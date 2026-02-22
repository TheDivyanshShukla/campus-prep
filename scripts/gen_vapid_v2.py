from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import base64

def generate_vapid_keys():
    # Generate an EC key on the P-256 curve (required for VAPID)
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    
    # Get raw private key bytes (32 bytes)
    priv_num = private_key.private_numbers().private_value
    priv_bytes = priv_num.to_bytes(32, byteorder='big')
    
    # Get raw public key bytes in uncompressed format (65 bytes)
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    private_b64 = base64.urlsafe_b64encode(priv_bytes).decode().strip('=')
    public_b64 = base64.urlsafe_b64encode(pub_bytes).decode().strip('=')
    
    print(f"VAPID_PRIVATE_KEY = '{private_b64}'")
    print(f"VAPID_PUBLIC_KEY = '{public_b64}'")

if __name__ == "__main__":
    generate_vapid_keys()
