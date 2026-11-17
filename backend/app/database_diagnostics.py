"""Map database failures to controlled messages; never expose driver error text."""

def database_failure(error):
    original=getattr(error,'orig',error)
    message=str(original).lower()
    sqlstate=getattr(original,'sqlstate',None)
    if sqlstate=='28P01' or 'password authentication failed' in message:
        return 'database_password_rejected','The saved database password was rejected by Supabase. An administrator must update the backend database connection.'
    if any(term in message for term in ('tenant or user not found','tenant not found')):
        return 'database_destination_invalid','Supabase could not find the configured database project or user. An administrator must check the connection string from Supabase Connect.'
    if any(term in message for term in ('timeout','timed out')):
        return 'database_timeout','The database connection timed out. Check the network connection, VPN or proxy, then try again.'
    if any(term in message for term in ('could not translate host name','getaddrinfo','name or service not known')):
        return 'database_dns_failure','The database hostname could not be resolved. Check the internet connection and saved Supabase connection settings.'
    if any(term in message for term in ('certificate verify failed','certificate verification failed','self-signed certificate')):
        return 'database_tls_failure','The secure database connection could not be verified. An administrator must check the TLS and certificate settings.'
    return 'database_unavailable','Cannot connect to the configured PostgreSQL database. Check the Supabase project, connection string and network.'
