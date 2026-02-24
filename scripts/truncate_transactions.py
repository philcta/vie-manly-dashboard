"""Delete all transactions from Supabase in batches, then insert from Square."""
import os, json, urllib.request, urllib.error, time
from dotenv import load_dotenv

load_dotenv()

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")


def supa_delete_batch(offset_id=0):
    """Delete a batch of rows with id > offset_id, return count deleted."""
    # First get IDs to delete
    url = f"{SUPA_URL}/rest/v1/transactions?select=id&id=gt.{offset_id}&order=id.asc&limit=1000"
    req = urllib.request.Request(url, headers={
        "apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}",
    })
    resp = urllib.request.urlopen(req, timeout=30)
    rows = json.loads(resp.read())
    
    if not rows:
        return 0, 0
    
    min_id = rows[0]["id"]
    max_id = rows[-1]["id"]
    
    # Delete this range
    del_url = f"{SUPA_URL}/rest/v1/transactions?id=gte.{min_id}&id=lte.{max_id}"
    del_req = urllib.request.Request(del_url, headers={
        "apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}",
        "Prefer": "return=minimal",
    }, method="DELETE")
    
    try:
        urllib.request.urlopen(del_req, timeout=60)
        return len(rows), max_id
    except urllib.error.HTTPError as e:
        print(f"  Delete error: {e.code} - {e.read().decode()[:200]}")
        return 0, max_id


def main():
    print("🗑️  Deleting all transactions from Supabase (in batches)...")
    
    total_deleted = 0
    last_id = 0
    
    while True:
        count, last_id = supa_delete_batch(last_id)
        if count == 0:
            break
        total_deleted += count
        print(f"\r  Deleted {total_deleted} rows (last id: {last_id})", end="", flush=True)
        time.sleep(0.2)  # Small delay to avoid rate limiting
    
    print(f"\n✅ Total deleted: {total_deleted} rows")
    
    # Verify
    url = f"{SUPA_URL}/rest/v1/transactions?select=id&limit=1"
    req = urllib.request.Request(url, headers={
        "apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}",
    })
    resp = urllib.request.urlopen(req, timeout=15)
    remaining = json.loads(resp.read())
    print(f"  Remaining rows: {len(remaining)}")


if __name__ == "__main__":
    main()
