REVOKE ALL PRIVILEGES, GRANT OPTION
    FROM 'school_reader'@'%';
GRANT SELECT ON school.*
    TO 'school_reader'@'%';
FLUSH PRIVILEGES;

