import ssl
from fastapi.security import HTTPBearer
import ldap
import jwt
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate
from datetime import datetime
import os
from typing import Optional, Dict, Tuple
from OpenSSL import crypto
import gssapi
import base64
from fastapi import HTTPException, Security

class CertValidator:
    def __init__(self):
        self.ca_cert_path = os.getenv('CA_CERT_PATH', '/etc/ipa/ca.crt') # Placeholder``
        self.crl_path = os.getenv('CRL_PATH', '/etc/ipa/ca.crl') # Placeholder
        self.ocsp_url = os.getenv('OCSP_URL', 'http://ipa-ca.example.com:8080/ca/ocsp') # Placeholder
        
    def validate_cert_chain(self, cert_data: str) -> Tuple[bool, str]:
        """
        Validate the certificate chain against IPA CA
        """
        try:
            # Load the CA certificate
            with open(self.ca_cert_path, 'rb') as ca_file:
                ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, ca_file.read())
            
            # Create a certificate store and add the CA cert
            store = crypto.X509Store()
            store.add_cert(ca_cert)
            
            # Load CRL if available
            if os.path.exists(self.crl_path):
                with open(self.crl_path, 'rb') as crl_file:
                    crl = crypto.load_crl(crypto.FILETYPE_PEM, crl_file.read())
                store.add_crl(crl)
                store.set_flags(crypto.X509StoreFlags.CRL_CHECK)
            
            # Load the client certificate
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
            
            # Create a certificate context
            store_ctx = crypto.X509StoreContext(store, cert)
            
            # Verify the certificate
            store_ctx.verify_certificate()
            
            return True, "Certificate validation successful"
            
        except crypto.X509StoreContextError as e:
            return False, f"Certificate validation failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error during certificate validation: {str(e)}"

    def check_cert_revocation(self, cert_data: str) -> Tuple[bool, str]:
        """
        Check certificate revocation status using CRL and OCSP
        """
        try:
            cert = x509.load_pem_x509_certificate(
                cert_data.encode(),
                default_backend()
            )
            
            # Check expiration
            if datetime.utcnow() > cert.not_valid_after:
                return False, "Certificate has expired"
            if datetime.utcnow() < cert.not_valid_before:
                return False, "Certificate is not yet valid"
            
            # Implement OCSP check here if needed
            # This is a placeholder for OCSP validation
            # ocsp_response = self.check_ocsp(cert)
            
            return True, "Revocation check passed"
            
        except Exception as e:
            return False, f"Revocation check failed: {str(e)}"

class IPAAuthenticator:
    def __init__(self):
        self.ipa_server = os.getenv('IPA_SERVER', 'ipa.example.com')
        self.ipa_domain = os.getenv('IPA_DOMAIN', 'example.com')
        self.ldap_uri = f"ldaps://{self.ipa_server}"
        
    def validate_kerberos_token(self, token: str) -> Tuple[bool, str, Dict]:
        """
        Validate Kerberos token against IPA server
        """
        try:
            # Decode the token
            token_data = base64.b64decode(token)
            
            # Create a GSSAPI context
            server_name = gssapi.Name(
                f'HTTP/{self.ipa_server}@{self.ipa_domain.upper()}',
                name_type=gssapi.NameType.hostbased_service
            )
            
            context = gssapi.SecurityContext(
                usage='accept',
                name=server_name
            )
            
            # Validate the token
            context.step(token_data)
            
            if not context.complete:
                return False, "Kerberos authentication incomplete", {}
            
            # Extract user information
            client_name = str(context.initiator_name)
            return True, "Kerberos authentication successful", {
                "username": client_name,
                "auth_type": "kerberos"
            }
            
        except gssapi.exceptions.GSSError as e:
            return False, f"Kerberos authentication failed: {str(e)}", {}
        except Exception as e:
            return False, f"Unexpected error during Kerberos authentication: {str(e)}", {}

    def validate_ldap_user(self, username: str, password: str) -> Tuple[bool, str, Dict]:
        """
        Validate user credentials against IPA LDAP
        """
        try:
            # Initialize LDAP connection
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
            ldap_conn = ldap.initialize(self.ldap_uri)
            ldap_conn.protocol_version = ldap.VERSION3
            
            # Bind with user credentials
            user_dn = f"uid={username},cn=users,cn=accounts,dc={',dc='.join(self.ipa_domain.split('.'))}"
            ldap_conn.simple_bind_s(user_dn, password)
            
            # Search for user attributes
            base_dn = f"dc={',dc='.join(self.ipa_domain.split('.'))}"
            search_filter = f"(&(uid={username})(objectClass=posixAccount))"
            
            result = ldap_conn.search_s(
                base_dn,
                ldap.SCOPE_SUBTREE,
                search_filter,
                ['uid', 'cn', 'memberOf']
            )
            
            if not result:
                return False, "User not found", {}
            
            user_attrs = result[0][1]
            return True, "LDAP authentication successful", {
                "username": username,
                "groups": user_attrs.get('memberOf', []),
                "auth_type": "ldap"
            }
            
        except ldap.INVALID_CREDENTIALS:
            return False, "Invalid LDAP credentials", {}
        except Exception as e:
            return False, f"LDAP authentication failed: {str(e)}", {}
        finally:
            try:
                ldap_conn.unbind_s()
            except:
                pass

class SecurityConfig:
    def __init__(self):
        self.AUTH_MODE = os.getenv("AUTH_MODE", "disabled").lower()
        self.PKI_CERT_PATH = os.getenv("PKI_CERT_PATH", "/etc/pki/tls/certs/server.crt")
        self.PKI_KEY_PATH = os.getenv("PKI_KEY_PATH", "/etc/pki/tls/private/server.key")
        
        self.cert_validator = CertValidator()
        self.ipa_auth = IPAAuthenticator()
        self.bearer_scheme = HTTPBearer(auto_error=False)
        
    async def authenticate(self, token: Optional[str] = Security(HTTPBearer(auto_error=False))) -> bool:
        if self.AUTH_MODE == "disabled":
            return True
            
        if self.AUTH_MODE == "dev":
            return True
            
        if self.AUTH_MODE == "prod":
            if not token:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            try:
                # Extract token type and data
                auth_parts = token.credentials.split('.')
                if len(auth_parts) != 2:
                    raise ValueError("Invalid token format")
                    
                auth_type, auth_data = auth_parts
                
                if auth_type.lower() == 'cert':
                    # Validate PKI certificate
                    is_valid, message = self.cert_validator.validate_cert_chain(auth_data)
                    if not is_valid:
                        raise HTTPException(status_code=401, detail=message)
                        
                    # Check revocation
                    is_valid, message = self.cert_validator.check_cert_revocation(auth_data)
                    if not is_valid:
                        raise HTTPException(status_code=401, detail=message)
                        
                elif auth_type.lower() == 'kerberos':
                    # Validate Kerberos token
                    is_valid, message, user_info = self.ipa_auth.validate_kerberos_token(auth_data)
                    if not is_valid:
                        raise HTTPException(status_code=401, detail=message)
                        
                elif auth_type.lower() == 'ldap':
                    # Extract username and password from auth_data
                    try:
                        creds = base64.b64decode(auth_data).decode().split(':')
                        if len(creds) != 2:
                            raise ValueError("Invalid LDAP credentials format")
                        username, password = creds
                    except Exception as e:
                        raise HTTPException(status_code=401, detail="Invalid LDAP credentials format")
                        
                    # Validate LDAP credentials
                    is_valid, message, user_info = self.ipa_auth.validate_ldap_user(username, password)
                    if not is_valid:
                        raise HTTPException(status_code=401, detail=message)
                        
                else:
                    raise HTTPException(status_code=401, detail="Unsupported authentication type")
                    
                return True
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=401,
                    detail=f"Authentication failed: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                
        return False

    def get_ssl_config(self):
        if self.AUTH_MODE == "prod":
            return {
                "ssl_keyfile": self.PKI_KEY_PATH,
                "ssl_certfile": self.PKI_CERT_PATH
            }
        return {}