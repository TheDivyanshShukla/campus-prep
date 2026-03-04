import os
import requests
import json
from pathlib import Path

# Load .env manually if not in environment
def load_env():
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ.setdefault(k, v)

def configure_rate_limits(zone_id, auth_token):
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    # 1. Global Rate Limit Rule (WAF Custom Rules)
    # Target: 100 requests / 1 minute
    # Action: Managed Challenge (to allow humans but stop bots)
    
    ruleset_data = {
        "rules": [
            {
                "action": "block",
                "description": "Consolidated Rate Limit: 20 req / 10s",
                "expression": "(http.request.uri.path contains \"/\")",
                "ratelimit": {
                    "characteristics": ["ip.src", "cf.colo.id"],
                    "period": 10,
                    "requests_per_period": 20,
                    "mitigation_timeout": 10
                },
                "enabled": True
            }
        ]
    }

    # First, we need to find the WAF 'http_ratelimit' phase ruleset ID for the zone
    print(f"Fetching rulesets for zone: {zone_id}...")
    response = requests.get(
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Error fetching rulesets: {response.status_code}")
        print(response.text)
        return

    rulesets = response.json().get("result", [])
    ratelimit_ruleset = next((r for r in rulesets if r['phase'] == 'http_ratelimit'), None)

    if not ratelimit_ruleset:
        # Create a ruleset if it doesn't exist
        print("Creating new http_ratelimit ruleset...")
        create_data = {
            "name": "Default Rate Limiting Ruleset",
            "description": "Created by Antigravity",
            "kind": "zone",
            "phase": "http_ratelimit",
            "rules": ruleset_data["rules"]
        }
        resp = requests.post(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets",
            headers=headers,
            json=create_data
        )
    else:
        # Update existing ruleset
        ruleset_id = ratelimit_ruleset['id']
        print(f"Fetching details for existing ruleset: {ruleset_id}...")
        
        # Get current rules to see what's there
        detail_resp = requests.get(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets/{ruleset_id}",
            headers=headers
        )
        if detail_resp.status_code == 200:
            existing_rules = detail_resp.json().get("result", {}).get("rules", [])
            print(f"Found {len(existing_rules)} existing rules in the ruleset.")
            for i, r in enumerate(existing_rules):
                print(f"  Rule {i+1}: {r.get('description', 'No description')}")
        
        print(f"Updating ruleset {ruleset_id} with 1 new consolidated rule...")
        # Direct PUT to the ruleset endpoint should replace the rules list
        resp = requests.put(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/rulesets/{ruleset_id}",
            headers=headers,
            json={
                "description": "Consolidated Rate Limiting for CampusPrep",
                "rules": ruleset_data["rules"]
            }
        )

    if resp.status_code in [200, 201]:
        print("Successfully configured Cloudflare rate limits.")
        print(json.dumps(resp.json(), indent=2))
    else:
        print(f"Failed to configure rate limits: {resp.status_code}")
        print(resp.text)

if __name__ == "__main__":
    load_env()
    auth_token = os.getenv("CF_AUTH_TOKEN")
    zone_id = os.getenv("CF_ZONE_ID")

    if not auth_token:
        print("Error: CF_AUTH_TOKEN not found in environment or .env")
    elif not zone_id:
        print("Error: CF_ZONE_ID not found. Please add CF_ZONE_ID to your .env file.")
    else:
        configure_rate_limits(zone_id, auth_token)
