let lastUpdated = Number(document.querySelector("#last-updated")?.textContent) || 0;
let wasStale = lastUpdated ? Date.now() / 1000 - lastUpdated > 900 : null;

async function refreshWhenDataChanges() {
  try {
    const response = await fetch("/api/v1/status/", { cache: "no-store" });
    if (!response.ok) return;
    const updated = Number((await response.json()).epoch_updated_at) || 0;
    const stale = updated ? Date.now() / 1000 - updated > 900 : true;
    if (lastUpdated && (updated !== lastUpdated || stale !== wasStale)) location.reload();
    lastUpdated = updated;
    wasStale = stale;
  } catch (_) {
    // The next poll retries without interrupting the page.
  }
}

setInterval(refreshWhenDataChanges, 60_000);
