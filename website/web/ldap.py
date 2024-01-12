from ldap3 import Server, Connection, SAFE_SYNC, Tls
from ldap3.core.exceptions import LDAPException, LDAPBindError
import ssl
from typing import Dict, Any

def global_ldap_authentication(user_name: str, user_pwd: str, ldap_config: Dict[str, Any]): # type: ignore[no-untyped-def]
    """
      Function: global_ldap_authentication
       Purpose: Make a connection to encrypted LDAP server.
       :params: ** Mandatory Positional Parameters
                1. user_name - LDAP user Name
                2. user_pwd - LDAP User Password
       :return: None
    """
    # fetch the username and password
    ldap_user_name = user_name.strip()
    ldap_user_pwd = user_pwd.strip()
    # ldap server hostname and port
    ldsp_server = ldap_config['server']
    # dn
    root_dn = ldap_config['root_dn']
    base_dn = ldap_config['base_dn']
    # user
    user = f'{base_dn}={ldap_user_name},{root_dn}'
    if ldap_config['verify']:
        tls_configuration = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=ldap_config['cert'])
    else :
        tls_configuration = Tls(validate=ssl.CERT_NONE)
    server = Server(ldsp_server,tls=tls_configuration)
    connection = Connection(server,
                            user=user,
                            password=ldap_user_pwd,
                            client_strategy=SAFE_SYNC
                            )
    connection.open()

    res = connection.bind()
    return res[0]
