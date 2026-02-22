from py_vapid import Vapid
import base64
from cryptography.hazmat.primitives import serialization

def generate_vapid_keys():
    vapid = Vapid()
    vapid.generate_keys()
    
    # Extract keys using cryptography primitives
    private_bytes = vapid.private_key.private_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    # The above is not exactly what VAPID needs. 
    # VAPID specifically needs the raw 32 bytes for private and 65 bytes for public (uncompressed point).
    
    # Let's try to find if there's a simpler way to get raw bytes from the vapid object
    # According to pywepush/vapid.py, it expects raw bytes.
    
    # If all else fails, I'll use pywebpush's internal helper if it exists.
    # Actually, let's just use the `wapid` cli tool if available or try to find the raw bytes.
    
    try:
        # Some versions have .private_key.to_string()
        priv_bytes = vapid.private_key.to_string()
        pub_bytes = vapid.public_key.to_string()
    except AttributeError:
        # Others might need to export to DER and slice, but that's complex.
        # Let's try to check the object directory
        # print(dir(vapid.private_key))
        # Usually for EC keys in cryptography:
        from cryptography.hazmat.primitives.asymmetric import ec
        priv_num = vapid.private_key.private_numbers().private_value
        priv_bytes = priv_num.to_bytes(32, byteorder='big')
        pub_bytes = vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )

    private_key = base64.urlsafe_b64encode(priv_bytes).decode().strip('=')
    public_key = base64.urlsafe_b64encode(pub_bytes).decode().strip('=')
    
    print(f"VAPID_PRIVATE_KEY = '{private_key}'")
    print(f"VAPID_PUBLIC_KEY = '{public_key}'")

if __name__ == "__main__":
    generate_vapid_keys()
