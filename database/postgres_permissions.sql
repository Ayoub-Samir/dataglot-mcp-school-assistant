CREATE ROLE school_reader LOGIN PASSWORD 'school_readonly_pass';
GRANT CONNECT ON DATABASE school TO school_reader;
GRANT USAGE ON SCHEMA public TO school_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO school_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO school_reader;

