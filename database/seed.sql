-- Sovereign AI Workbench - Seed Data
-- Roles, Permissions, Departments (no user passwords)

-- Departments
INSERT INTO departments (id, name, display_name, description) VALUES
    ('d0000001-0000-0000-0000-000000000001', 'administration', 'Administration', 'System administration and IT'),
    ('d0000001-0000-0000-0000-000000000002', 'human_resources', 'Human Resources', 'HR department'),
    ('d0000001-0000-0000-0000-000000000003', 'engineering', 'Engineering', 'Engineering and technical operations'),
    ('d0000001-0000-0000-0000-000000000004', 'security', 'Security', 'Information security and compliance'),
    ('d0000001-0000-0000-0000-000000000005', 'operations', 'Operations', 'Plant operations and maintenance')
ON CONFLICT (name) DO NOTHING;

-- Roles
INSERT INTO roles (id, name, display_name, description, is_system) VALUES
    ('r0000001-0000-0000-0000-000000000001', 'system_admin', 'System Administrator', 'Full system access and configuration', TRUE),
    ('r0000001-0000-0000-0000-000000000002', 'security_admin', 'Security Administrator', 'Security monitoring and audit access', TRUE),
    ('r0000001-0000-0000-0000-000000000003', 'hr_manager', 'HR Manager', 'Human resources management access', FALSE),
    ('r0000001-0000-0000-0000-000000000004', 'engineering_manager', 'Engineering Manager', 'Engineering document and team access', FALSE),
    ('r0000001-0000-0000-0000-000000000005', 'senior_engineer', 'Senior Engineer', 'Extended engineering access', FALSE),
    ('r0000001-0000-0000-0000-000000000006', 'employee', 'Employee', 'Standard employee access', FALSE),
    ('r0000001-0000-0000-0000-000000000007', 'auditor', 'Auditor', 'Read-only audit and compliance access', FALSE)
ON CONFLICT (name) DO NOTHING;

-- Permissions
INSERT INTO permissions (id, name, display_name, description, category) VALUES
    -- Document permissions
    ('p0000001-0000-0000-0000-000000000001', 'view_documents', 'View Documents', 'View authorized documents', 'documents'),
    ('p0000001-0000-0000-0000-000000000002', 'search_documents', 'Search Documents', 'Search within authorized documents', 'documents'),
    ('p0000001-0000-0000-0000-000000000003', 'upload_documents', 'Upload Documents', 'Upload new documents', 'documents'),
    ('p0000001-0000-0000-0000-000000000004', 'download_documents', 'Download Documents', 'Download authorized documents', 'documents'),
    ('p0000001-0000-0000-0000-000000000005', 'manage_documents', 'Manage Documents', 'Manage document permissions and classification', 'documents'),
    -- AI permissions
    ('p0000001-0000-0000-0000-000000000006', 'use_ai', 'Use AI', 'Access AI workbench for queries', 'ai'),
    ('p0000001-0000-0000-0000-000000000007', 'use_vision', 'Use Vision', 'Use vision/image analysis capabilities', 'ai'),
    ('p0000001-0000-0000-0000-000000000008', 'use_audio', 'Use Audio', 'Use audio transcription capabilities', 'ai'),
    ('p0000001-0000-0000-0000-000000000009', 'use_video', 'Use Video', 'Use video processing capabilities', 'ai'),
    ('p0000001-0000-0000-0000-000000000010', 'execute_code', 'Execute Code', 'Run code in sandbox', 'ai'),
    ('p0000001-0000-0000-0000-000000000011', 'generate_files', 'Generate Files', 'Generate DOCX/PPTX/XLSX/PDF files', 'ai'),
    -- Administration permissions
    ('p0000001-0000-0000-0000-000000000012', 'manage_users', 'Manage Users', 'Create, edit, disable users', 'admin'),
    ('p0000001-0000-0000-0000-000000000013', 'manage_roles', 'Manage Roles', 'Create and modify roles', 'admin'),
    ('p0000001-0000-0000-0000-000000000014', 'manage_models', 'Manage Models', 'Register, enable, disable AI models', 'admin'),
    ('p0000001-0000-0000-0000-000000000015', 'view_audit', 'View Audit Log', 'Access audit event history', 'security'),
    ('p0000001-0000-0000-0000-000000000016', 'manage_security', 'Manage Security', 'Configure security settings and network policies', 'security'),
    ('p0000001-0000-0000-0000-000000000017', 'view_hardware', 'View Hardware', 'View system hardware status', 'system'),
    ('p0000001-0000-0000-0000-000000000018', 'manage_system', 'Manage System', 'System configuration and diagnostics', 'system'),
    ('p0000001-0000-0000-0000-000000000019', 'approve_agent_actions', 'Approve Agent Actions', 'Approve or reject Human-in-the-Loop agent actions', 'ai')
ON CONFLICT (name) DO NOTHING;

-- Role-Permission mappings

-- System Admin: all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 'r0000001-0000-0000-0000-000000000001', id FROM permissions
ON CONFLICT DO NOTHING;

-- Security Admin: security + audit + view
INSERT INTO role_permissions (role_id, permission_id)
SELECT 'r0000001-0000-0000-0000-000000000002', id FROM permissions
WHERE name IN ('view_documents', 'search_documents', 'view_audit', 'manage_security', 'view_hardware', 'use_ai')
ON CONFLICT DO NOTHING;

-- HR Manager: documents + AI + users
INSERT INTO role_permissions (role_id, permission_id)
SELECT 'r0000001-0000-0000-0000-000000000003', id FROM permissions
WHERE name IN ('view_documents', 'search_documents', 'upload_documents', 'download_documents', 'manage_documents', 'use_ai', 'use_vision', 'generate_files', 'manage_users')
ON CONFLICT DO NOTHING;

-- Engineering Manager: documents + AI + code
INSERT INTO role_permissions (role_id, permission_id)
SELECT 'r0000001-0000-0000-0000-000000000004', id FROM permissions
WHERE name IN ('view_documents', 'search_documents', 'upload_documents', 'download_documents', 'manage_documents', 'use_ai', 'use_vision', 'use_audio', 'use_video', 'execute_code', 'generate_files')
ON CONFLICT DO NOTHING;

-- Senior Engineer: documents + AI + code
INSERT INTO role_permissions (role_id, permission_id)
SELECT 'r0000001-0000-0000-0000-000000000005', id FROM permissions
WHERE name IN ('view_documents', 'search_documents', 'upload_documents', 'download_documents', 'use_ai', 'use_vision', 'use_audio', 'execute_code', 'generate_files')
ON CONFLICT DO NOTHING;

-- Employee: basic access
INSERT INTO role_permissions (role_id, permission_id)
SELECT 'r0000001-0000-0000-0000-000000000006', id FROM permissions
WHERE name IN ('view_documents', 'search_documents', 'download_documents', 'use_ai', 'generate_files')
ON CONFLICT DO NOTHING;

-- Auditor: read-only audit
INSERT INTO role_permissions (role_id, permission_id)
SELECT 'r0000001-0000-0000-0000-000000000007', id FROM permissions
WHERE name IN ('view_documents', 'search_documents', 'view_audit', 'view_hardware')
ON CONFLICT DO NOTHING;

-- System config defaults
INSERT INTO system_config (key, value) VALUES
    ('app.name', '"Sovereign AI Workbench"'),
    ('app.mode', '"development"'),
    ('security.max_failed_attempts', '5'),
    ('security.lockout_duration_minutes', '30'),
    ('security.session_timeout_hours', '8'),
    ('security.air_gapped_mode', 'false'),
    ('quotas.max_upload_size_mb', '500'),
    ('quotas.max_concurrent_jobs', '3'),
    ('quotas.max_sandbox_time_seconds', '30'),
    ('quotas.max_storage_gb', '10'),
    ('models.auto_discover', 'true'),
    ('models.health_check_interval_seconds', '60')
ON CONFLICT (key) DO NOTHING;
