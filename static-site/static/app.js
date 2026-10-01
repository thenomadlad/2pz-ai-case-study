const ACTION_COLORS = { PROTECT: "#2e7d32", HOLD: "#f9a825", SHRINK: "#c62828" };

const map = L.map("map").setView([25.2048, 55.2708], 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

let branches = [];
let communities = [];
let network = {};
const branchMarkers = {};
let communityLayer = L.layerGroup();
let assignmentLineLayer = L.layerGroup();
let siblingLineLayer = L.layerGroup();
let diffData = null;
let diffHighlightLayer = L.layerGroup();

function popRadius(pop) {
  return Math.max(6, Math.min(30, Math.sqrt(pop) / 8));
}

function shortBranchName(name) {
  // Real seed branch names all start with "Bedashing Beauty Lounge ", which at default
  // zoom makes permanent map labels overlap and clutter central Dubai. Strip that prefix
  // for the map label only (side panel keeps the full name). Falls back to the full name
  // if the prefix isn't present.
  return name.replace(/^bedashing beauty lounge /i, "");
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value === null || value === undefined ? "" : String(value);
  return div.innerHTML;
}

function fmt(value, isEstimated) {
  if (value === null || value === undefined) return "n/a";
  const text = escapeHtml(typeof value === "number" ? value.toLocaleString() : value);
  return isEstimated ? `<span class="estimated">~${text}</span>` : text;
}

function formatChangedFieldRow(field, delta) {
  const label = escapeHtml(field);
  const oldValue = escapeHtml(delta.old);
  const newValue = escapeHtml(delta.new);
  return `<tr><td>${label}</td><td><span class="diff-old">${oldValue}</span> &rarr; <span class="diff-new">${newValue}</span></td></tr>`;
}

function formatActionChangeRow(diffEntry) {
  // The single most important thing this panel needs to surface: what the decision
  // actually flipped TO. changed_fields only covers BranchFeatures fields, never the
  // Decision fields (action/confidence), so without this the side panel shows no
  // indication anywhere of an action flip. Routed through escapeHtml like
  // formatChangedFieldRow -- no unescaped interpolation.
  const oldAction = escapeHtml(diffEntry.old.action);
  const newAction = escapeHtml(diffEntry.new.action);
  const oldConfidence = escapeHtml(diffEntry.old.confidence);
  const newConfidence = escapeHtml(diffEntry.new.confidence);
  return `<tr><td>Decision</td><td><span class="diff-old">${oldAction} (${oldConfidence})</span> &rarr; <span class="diff-new">${newAction} (${newConfidence})</span></td></tr>`;
}

function renderDiffSection(diffEntry) {
  if (!diffEntry) return "";
  const hasChanges = diffEntry.action_changed || Object.keys(diffEntry.changed_fields).length > 0;
  if (!hasChanges) return "";
  let rowsHtml;
  if (diffEntry.old === null) {
    rowsHtml = '<tr><td colspan="2">New in this scenario</td></tr>';
  } else {
    const actionRow = diffEntry.action_changed && diffEntry.old && diffEntry.new
      ? formatActionChangeRow(diffEntry) : "";
    rowsHtml = actionRow + Object.entries(diffEntry.changed_fields)
      .map(([field, delta]) => formatChangedFieldRow(field, delta)).join("");
  }
  return `
    <div class="diff-section">
      <h4>Changed since baseline</h4>
      <table>${rowsHtml}</table>
    </div>
  `;
}

function renderSidePanel(branch, diffEntry) {
  diffEntry = diffEntry || diffEntryFor(branch.branch_id);
  const panel = document.getElementById("side-panel");
  const est = new Set(branch.estimated_fields || []);
  const rows = [
    ["Female population served", branch.female_pop_served, est.has("female_pop_served"), network.female_pop_served_median],
    ["Contested share", branch.contested_share.toFixed(2), est.has("contested_share"), network.contested_share_median?.toFixed(2)],
    ["Avg price (AED)", branch.avg_price_aed, est.has("avg_price_aed"), network.avg_price_aed_median],
    ["Rating", branch.rating, est.has("rating"), network.rating_median],
    ["Communities served", branch.communities_served, est.has("communities_served"), null],
    ["Mean distance (km)", branch.mean_distance_km?.toFixed?.(2) ?? branch.mean_distance_km, est.has("mean_distance_km"), null],
    ["Contested pop", branch.contested_pop, est.has("contested_pop"), null],
    ["Nearest sibling (km)", branch.nearest_sibling_km?.toFixed?.(2) ?? branch.nearest_sibling_km, est.has("nearest_sibling_km"), null],
    ["Siblings within 5km", branch.siblings_within_5km, est.has("siblings_within_5km"), null],
    ["Price index", branch.price_index?.toFixed?.(2) ?? branch.price_index, est.has("price_index"), null],
    ["Pop-per-1k rank", branch.pop_per_1k_rank, est.has("pop_per_1k_rank"), null],
  ];
  panel.innerHTML = `
    <button class="close-panel" aria-label="Close">&times;</button>
    <h3>${escapeHtml(branch.name)}</h3>
    <p><strong>${escapeHtml(branch.action)}</strong> (${escapeHtml(branch.confidence)} confidence)</p>
    <p>${escapeHtml(branch.rationale)}</p>
    <p><strong>Key drivers:</strong> ${escapeHtml((branch.key_drivers || []).join(", "))}</p>
    <table>
      <tr><th>Feature</th><th>Value</th><th>Network median</th></tr>
      ${rows.map(([label, value, isEst, median]) =>
        `<tr><td>${escapeHtml(label)}</td><td>${fmt(value, isEst)}</td><td>${escapeHtml(median ?? "n/a")}</td></tr>`
      ).join("")}
    </table>
    <p><strong>Caveats:</strong> ${escapeHtml((branch.caveats || []).join("; ") || "none")}</p>
    ${renderDiffSection(diffEntry)}
  `;
  panel.querySelector(".close-panel").addEventListener("click", () => {
    panel.classList.add("hidden");
  });
  panel.classList.remove("hidden");
}

function drawSiblingLinks(branch) {
  siblingLineLayer.clearLayers();
  for (const other of branches) {
    if (other.branch_id === branch.branch_id) continue;
    const dLat = branch.lat - other.lat;
    const dLng = branch.lng - other.lng;
    const kmApprox = Math.sqrt(dLat * dLat + dLng * dLng) * 111;
    if (kmApprox <= 5) {
      const line = L.polyline([[branch.lat, branch.lng], [other.lat, other.lng]],
        { color: "#555", weight: 1, dashArray: "4 4" });
      line.bindTooltip(`${kmApprox.toFixed(1)} km`, { permanent: true });
      siblingLineLayer.addLayer(line);
    }
  }
}

function renderBranches() {
  for (const branch of branches) {
    const marker = L.circleMarker([branch.lat, branch.lng], {
      radius: popRadius(branch.female_pop_served),
      color: ACTION_COLORS[branch.action] || "#999",
      fillColor: ACTION_COLORS[branch.action] || "#999",
      fillOpacity: 0.7,
    }).addTo(map);
    marker.bindTooltip(`${escapeHtml(shortBranchName(branch.name))} (${escapeHtml(branch.action)})`,
      { permanent: true, direction: "top" });
    marker.on("click", () => {
      renderSidePanel(branch, diffEntryFor(branch.branch_id));
      drawSiblingLinks(branch);
      siblingLineLayer.addTo(map);
    });
    branchMarkers[branch.branch_id] = marker;
  }
}

function renderCommunities() {
  const branchById = Object.fromEntries(branches.map(b => [b.branch_id, b]));
  for (const community of communities) {
    const target = branchById[community.nearest_branch_id];
    const color = target ? (ACTION_COLORS[target.action] || "#999") : "#999";
    const dot = L.circleMarker([community.lat ?? 0, community.lng ?? 0], {
      radius: 4, color, fillColor: color,
      fillOpacity: Math.min(1, Math.max(0.2, community.female_pop / 20000)),
    });
    communityLayer.addLayer(dot);

    if (target) {
      const line = L.polyline(
        [[community.lat ?? 0, community.lng ?? 0], [target.lat, target.lng]],
        { color: "#888", weight: 0.5 }
      );
      assignmentLineLayer.addLayer(line);
    }
  }
}

function diffEntryFor(branchId) {
  if (!diffData) return null;
  return diffData.branches.find(d => d.branch_id === branchId) || null;
}

function renderDiffHighlights() {
  const branchById = Object.fromEntries(branches.map(b => [b.branch_id, b]));
  const communityById = Object.fromEntries(communities.map(c => [c.community_id, c]));

  for (const entry of diffData.branches) {
    if (entry.old === null && entry.new !== null) {
      // New branch introduced by the scenario -- not in /api/branches at all.
      const marker = L.circleMarker([entry.new.lat, entry.new.lng], {
        radius: popRadius(entry.new.female_pop_served || 0),
        color: ACTION_COLORS[entry.new.action] || "#999",
        fillColor: ACTION_COLORS[entry.new.action] || "#999",
        fillOpacity: 0.5,
        dashArray: "4 4",
        weight: 2,
      });
      marker.bindTooltip(`${escapeHtml(shortBranchName(entry.new.name))} (new, ${escapeHtml(entry.new.action)})`,
        { permanent: true, direction: "top" });
      marker.on("click", () => renderSidePanel(entry.new, entry));
      diffHighlightLayer.addLayer(marker);
    } else if (entry.action_changed || Object.keys(entry.changed_fields).length > 0) {
      const branch = branchById[entry.branch_id];
      if (!branch) continue;
      // A real decision flip gets a thicker ring colored by the NEW action -- visually
      // distinct from a branch whose feature values merely nudged without flipping the
      // decision (subtler plain dashed black ring, as before).
      const ring = entry.action_changed
        ? L.circleMarker([branch.lat, branch.lng], {
            radius: popRadius(branch.female_pop_served) + 6,
            color: ACTION_COLORS[entry.new.action] || "#000",
            weight: 4, dashArray: "3 3", fill: false,
          })
        : L.circleMarker([branch.lat, branch.lng], {
            radius: popRadius(branch.female_pop_served) + 5,
            color: "#000", weight: 2, dashArray: "2 4", fill: false,
          });
      diffHighlightLayer.addLayer(ring);

      // Relocation: show the new position too, not just a ring sitting at the old spot.
      const latChange = entry.changed_fields.lat;
      const lngChange = entry.changed_fields.lng;
      if (latChange || lngChange) {
        const oldLat = latChange ? latChange.old : branch.lat;
        const oldLng = lngChange ? lngChange.old : branch.lng;
        const newLat = entry.new.lat;
        const newLng = entry.new.lng;
        const moveLine = L.polyline([[oldLat, oldLng], [newLat, newLng]], {
          color: "#1565c0", weight: 3, dashArray: "1 6", lineCap: "round",
        });
        diffHighlightLayer.addLayer(moveLine);
        const newMarker = L.circleMarker([newLat, newLng], {
          radius: 6, color: "#1565c0", fillColor: "#1565c0", fillOpacity: 0.9, weight: 2,
        });
        newMarker.bindTooltip(`${escapeHtml(shortBranchName(entry.new.name))} (relocated here)`,
          { direction: "top" });
        diffHighlightLayer.addLayer(newMarker);
      }
    }
  }

  for (const entry of diffData.communities) {
    if (!entry.reassigned) continue;
    const community = communityById[entry.community_id];
    if (!community) continue;
    const ring = L.circleMarker([community.lat ?? 0, community.lng ?? 0], {
      radius: 7, color: "#000", weight: 2, dashArray: "2 4", fill: false,
    });
    diffHighlightLayer.addLayer(ring);
  }
}

function showLoadError(message) {
  const banner = document.getElementById("error-banner");
  banner.textContent = message;
  banner.classList.remove("hidden");
}

async function fetchJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`${url} returned ${resp.status}`);
  }
  return resp.json();
}

async function main() {
  try {
    const [branchResp, communityResp, networkPayload, diffPayload] = await Promise.all([
      fetchJson("/api/branches"), fetchJson("/api/communities"), fetchJson("/api/network"),
      fetchJson("/api/diff"),
    ]);
    branches = branchResp;
    communities = communityResp;
    network = networkPayload.stats;
    if (diffPayload.available) {
      diffData = diffPayload;
    }

    document.getElementById("backend-label").textContent = `backend: ${networkPayload.model_backend}`;
    document.getElementById("sources-label").textContent =
      `sources: branches=${networkPayload.data_sources.branches}, communities=${networkPayload.data_sources.communities}`;
    document.getElementById("run-at-label").textContent = `run at: ${networkPayload.pipeline_run_at}`;

    renderBranches();
    renderCommunities();
    communityLayer.addTo(map);

    document.getElementById("toggle-communities").addEventListener("change", (e) => {
      if (e.target.checked) communityLayer.addTo(map); else map.removeLayer(communityLayer);
    });
    document.getElementById("toggle-assignment-lines").addEventListener("change", (e) => {
      if (e.target.checked) assignmentLineLayer.addTo(map); else map.removeLayer(assignmentLineLayer);
    });
    document.getElementById("assumptions-toggle").addEventListener("click", () => {
      document.getElementById("assumptions-panel").classList.toggle("hidden");
    });

    if (diffData) {
      renderDiffHighlights();
      document.getElementById("toggle-diff").disabled = false;
      document.getElementById("toggle-diff").addEventListener("change", (e) => {
        if (e.target.checked) diffHighlightLayer.addTo(map); else map.removeLayer(diffHighlightLayer);
      });

      // Fix 7: if baseline and the scenario were decided by different backends, every
      // action flip in the diff conflates "inputs changed" with "decision method changed".
      // Keep this simple -- a single visible warning line, not a modal.
      if (diffData.baseline_backend && diffData.current_backend
          && diffData.baseline_backend !== diffData.current_backend) {
        const mismatchLabel = document.getElementById("backend-mismatch-label");
        mismatchLabel.textContent =
          `warning: comparing baseline (${diffData.baseline_backend}) vs scenario (${diffData.current_backend}) -- mixed backends`;
        mismatchLabel.classList.remove("hidden");
      }
    }
  } catch (err) {
    console.error("Failed to load pipeline data", err);
    showLoadError("Failed to load pipeline data — run `just all` first.");
  }
}

main();
