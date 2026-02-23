from django.conf import settings

def clerk_settings(request):
    """
    Exposes Clerk keys to templates.
    """
    # CLERK_JS_URL is derived from the publishable key for now 
    # as per standard Clerk frontend setup if not specified.
    # However, it's safer to just provide the key and let the frontend handle it
    # or expose the specific URL if needed.
    
    # Example PK: pk_test_ZW5hYmxpbmctYmlzb24tMjguY2xlcmsuYWNjb3VudHMuZGV2JA
    # The URL is enabling-bison-28.clerk.accounts.dev
    
    publishable_key = settings.CLERK_PUBLISHABLE_KEY
    js_url = "clerk.accounts.dev" # Default
    
    if publishable_key and "_" in publishable_key:
        try:
            # Clerk PK format: pk_[test/live]_<base64_encoded_domain>
            parts = publishable_key.split('_')
            if len(parts) >= 3:
                encoded_domain = parts[2]
                import base64
                # Add padding if necessary
                padding = '=' * (4 - len(encoded_domain) % 4)
                decoded = base64.b64decode(encoded_domain + padding).decode('utf-8')
                # Remove trailing $ or other characters if they exist
                if '$' in decoded:
                    js_url = decoded.split('$')[0]
                else:
                    js_url = decoded
        except Exception as e:
            print(f"Error extracting Clerk JS URL: {e}")

    return {
        'CLERK_PUBLISHABLE_KEY': settings.CLERK_PUBLISHABLE_KEY,
        'CLERK_JS_URL': js_url,
    }
