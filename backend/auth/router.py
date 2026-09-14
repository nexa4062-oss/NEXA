import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.schemas import LoginRequest, TokenResponse
from auth.service import AuthService, get_current_user
from auth.passwords import password_hasher
from models.orm import User, Role, Department, Permission, RolePermission
from audit.service import AuditService

router = APIRouter()


class FirstRunSetup(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)
    display_name: str
    employee_id: str
    email: str = ""
    organization_name: str = "Default Organization"


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    audit_service = AuditService(db)

    user = await auth_service.authenticate(login_data.username, login_data.password)

    if not user:
        await audit_service.log(
            action="login_failed",
            details={"username": login_data.username},
            ip_address=request.client.host if request.client else None,
            severity="warning",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    access_token = auth_service.create_access_token(user)
    refresh_token = auth_service.create_refresh_token(user)
    await auth_service.create_session(user, access_token)

    await audit_service.log(
        user_id=user.id,
        action="login",
        details={"username": user.username},
        ip_address=request.client.host if request.client else None,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
    )


@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    audit_service = AuditService(db)

    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    await auth_service.invalidate_session(token)

    await audit_service.log(
        user_id=user.id,
        action="logout",
        ip_address=request.client.host if request.client else None,
    )

    return {"message": "Logged out"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = AuthService.decode_token(token)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    from sqlalchemy import select
    from models.orm import User as UserModel
    import uuid

    stmt = select(UserModel).where(UserModel.id == uuid.UUID(payload["sub"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    auth_service = AuthService(db)
    access_token = auth_service.create_access_token(user)
    refresh_token = auth_service.create_refresh_token(user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    permissions = set()
    if user.role and user.role.permissions:
        for rp in user.role.permissions:
            if rp.permission:
                permissions.add(rp.permission.name)
    if user.permissions:
        for up in user.permissions:
            if up.permission:
                permissions.add(up.permission.name)

    return {
        "id": str(user.id),
        "employee_id": user.employee_id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "department": user.department.name if user.department else None,
        "designation": user.designation,
        "role": user.role.name if user.role else None,
        "role_display": user.role.display_name if user.role else None,
        "permissions": list(permissions),
        "status": user.status.value,
    }


@router.get("/setup-status")
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count()).select_from(User))
    has_demo = await db.scalar(
        select(func.count()).select_from(User).where(User.username == "admin_demo")
    )
    return {"needs_setup": count == 0, "has_demo_accounts": has_demo > 0}


@router.post("/setup")
async def first_run_setup(
    data: FirstRunSetup,
    db: AsyncSession = Depends(get_db),
):
    count = await db.scalar(select(func.count()).select_from(User))
    if count > 0:
        raise HTTPException(status_code=400, detail="Setup already completed")

    ALL_PERMISSIONS = [
        ("ai_chat", "AI Chat", "ai"),
        ("generate_files", "Generate Files", "ai"),
        ("execute_code", "Code Sandbox", "ai"),
        ("ai_rag_query", "RAG Query", "ai"),
        ("search_documents", "Search Documents", "documents"),
        ("view_documents", "View Documents", "documents"),
        ("upload_documents", "Upload Documents", "documents"),
        ("delete_documents", "Delete Documents", "documents"),
        ("manage_document_permissions", "Manage Document Permissions", "documents"),
        ("manage_models", "Manage Models", "models"),
        ("manage_users", "Manage Users", "admin"),
        ("manage_roles", "Manage Roles", "admin"),
        ("view_audit", "View Audit Logs", "admin"),
        ("system_settings", "System Settings", "admin"),
        ("manage_security", "Manage Security", "security"),
        ("hardware_view", "View Hardware", "system"),
        ("jobs_view", "View Jobs", "system"),
        ("approve_agent_actions", "Approve Agent Actions", "ai"),
    ]

    perm_objects = []
    for name, display, category in ALL_PERMISSIONS:
        p = Permission(id=uuid.uuid4(), name=name, display_name=display, category=category)
        db.add(p)
        perm_objects.append(p)

    admin_role = Role(
        id=uuid.uuid4(),
        name="super_admin",
        display_name="Super Administrator",
        description="Full system access",
        is_system=True,
    )
    db.add(admin_role)

    for perm in perm_objects:
        rp = RolePermission(id=uuid.uuid4(), role_id=admin_role.id, permission_id=perm.id)
        db.add(rp)

    dept = Department(id=uuid.uuid4(), name=data.organization_name, description="Primary organization")
    db.add(dept)

    admin_user = User(
        id=uuid.uuid4(),
        employee_id=data.employee_id,
        username=data.username,
        display_name=data.display_name,
        email=data.email,
        department_id=dept.id,
        designation="System Administrator",
        role_id=admin_role.id,
        password_hash=password_hasher.hash(data.password),
    )
    db.add(admin_user)
    await db.commit()

    return {
        "message": "Setup complete",
        "user_id": str(admin_user.id),
        "username": admin_user.username,
        "role": "super_admin",
    }


DEMO_ROLES = {
    "hr_manager": {
        "display_name": "HR Manager",
        "description": "Human Resources management access",
        "permissions": [
            "ai_chat", "generate_files", "view_documents", "upload_documents",
            "search_documents", "ai_rag_query",
        ],
    },
    "department_manager": {
        "display_name": "Department Manager",
        "description": "Department-level management access",
        "permissions": [
            "ai_chat", "generate_files", "execute_code", "view_documents",
            "upload_documents", "search_documents", "ai_rag_query",
            "view_audit", "hardware_view", "approve_agent_actions",
        ],
    },
    "engineer": {
        "display_name": "Engineer",
        "description": "Technical engineering access",
        "permissions": [
            "ai_chat", "generate_files", "execute_code", "view_documents",
            "upload_documents", "search_documents", "ai_rag_query",
        ],
    },
    "finance": {
        "display_name": "Finance User",
        "description": "Financial document access",
        "permissions": [
            "ai_chat", "generate_files", "view_documents", "search_documents",
            "ai_rag_query",
        ],
    },
    "reviewer": {
        "display_name": "Document Reviewer",
        "description": "Read-only document review access",
        "permissions": [
            "ai_chat", "view_documents", "search_documents", "ai_rag_query",
        ],
    },
}

DEMO_ACCOUNTS = [
    {"username": "admin_demo", "employee_id": "DEMO-ADM-001", "display_name": "Demo Administrator",
     "designation": "System Administrator", "role": "super_admin", "department": "IT"},
    {"username": "hr_manager_demo", "employee_id": "DEMO-HR-001", "display_name": "Priya Sharma",
     "designation": "HR Manager", "role": "hr_manager", "department": "Human Resources"},
    {"username": "manager_demo", "employee_id": "DEMO-MGR-001", "display_name": "Rajesh Kumar",
     "designation": "Department Manager", "role": "department_manager", "department": "Operations"},
    {"username": "engineer_demo", "employee_id": "DEMO-ENG-001", "display_name": "Ankit Patel",
     "designation": "Senior Engineer", "role": "engineer", "department": "Engineering"},
    {"username": "finance_demo", "employee_id": "DEMO-FIN-001", "display_name": "Meera Iyer",
     "designation": "Finance Analyst", "role": "finance", "department": "Finance"},
    {"username": "reviewer_demo", "employee_id": "DEMO-REV-001", "display_name": "Suresh Nair",
     "designation": "Quality Reviewer", "role": "reviewer", "department": "Quality"},
]

DEMO_DOCUMENTS = [
    {"filename": "employee_handbook.pdf", "classification": "internal",
     "content": "Employee Handbook 2026\n\nChapter 1: Organization Policies\nAll employees must adhere to workplace safety guidelines.\nLeave policy: 24 days earned leave, 12 days sick leave.\n\nChapter 2: Code of Conduct\nMaintain professional behavior at all times.",
     "allowed_roles": ["hr_manager", "super_admin", "department_manager"]},
    {"filename": "engineering_sop.pdf", "classification": "confidential",
     "content": "Engineering Standard Operating Procedures\n\nSection 1: Equipment Maintenance\nDaily inspection checklist for all rotating equipment.\nVibration analysis must be performed weekly.\n\nSection 2: Safety Protocols\nPermit-to-work required for all hot work activities.",
     "allowed_roles": ["engineer", "department_manager", "super_admin"]},
    {"filename": "financial_forecast_q3.xlsx", "classification": "restricted",
     "content": "Q3 Financial Forecast\n\nRevenue projection: 2400 crores\nOperational expenses: 1850 crores\nCapital expenditure: 320 crores\nNet margin target: 9.6%\n\nRisk factors: crude price volatility, maintenance shutdown.",
     "allowed_roles": ["finance", "department_manager", "super_admin"]},
    {"filename": "general_safety_guidelines.pdf", "classification": "public",
     "content": "General Safety Guidelines\n\nFire safety: Know your nearest exit.\nEmergency assembly point: Main gate area.\nFirst aid kits located at every floor.\nReport all incidents immediately to safety officer.",
     "allowed_roles": []},
    {"filename": "confidential_board_strategy.pdf", "classification": "highly_restricted",
     "content": "Board Strategy Document Q4 2026\n\nExpansion plan: New petrochemical unit.\nBudget allocation: 3200 crores over 3 years.\nTarget commissioning: Q2 2029.\nKey risks: Environmental clearance, land acquisition.",
     "allowed_roles": ["super_admin", "department_manager"]},
    {"filename": "quality_inspection_report.pdf", "classification": "internal",
     "content": "Quality Inspection Report - August 2026\n\nUnit 5 turnaround inspection complete.\nCorrosion mapping: Within acceptable limits.\nThickness readings: All above minimum.\nRecommendation: Continue monitoring quarterly.",
     "allowed_roles": ["engineer", "reviewer", "department_manager", "super_admin"]},
    {"filename": "hr_recruitment_plan.pdf", "classification": "confidential",
     "content": "Recruitment Plan 2026-2027\n\nOpen positions: 45 across engineering and operations.\nBudget: 2.8 crores for recruitment.\nTarget completion: March 2027.\nPriority: Process engineers, instrumentation specialists.",
     "allowed_roles": ["hr_manager", "super_admin"]},
]

DEMO_PASSWORD = "DemoPass@2026!"


@router.post("/seed-demo")
async def seed_demo_accounts(
    db: AsyncSession = Depends(get_db),
):
    """Seed demo accounts for hackathon/evaluation. Only works once."""
    existing = await db.scalar(
        select(func.count()).select_from(User).where(User.username == "admin_demo")
    )
    if existing > 0:
        return {"message": "Demo accounts already exist", "seeded": False}

    user_count = await db.scalar(select(func.count()).select_from(User))
    if user_count == 0:
        return {"message": "Run /api/auth/setup first to create admin", "seeded": False}

    all_perms = {}
    perm_result = await db.execute(select(Permission))
    for p in perm_result.scalars().all():
        all_perms[p.name] = p

    departments = {}
    dept_names = set(a["department"] for a in DEMO_ACCOUNTS)
    for dname in dept_names:
        existing_dept = await db.execute(select(Department).where(Department.name == dname))
        dept = existing_dept.scalar_one_or_none()
        if not dept:
            dept = Department(id=uuid.uuid4(), name=dname, description=f"{dname} department")
            db.add(dept)
        departments[dname] = dept

    await db.flush()

    admin_role_result = await db.execute(select(Role).where(Role.name == "super_admin"))
    admin_role = admin_role_result.scalar_one_or_none()

    roles_map = {"super_admin": admin_role}
    for role_name, role_def in DEMO_ROLES.items():
        existing_role = await db.execute(select(Role).where(Role.name == role_name))
        role = existing_role.scalar_one_or_none()
        if not role:
            role = Role(
                id=uuid.uuid4(),
                name=role_name,
                display_name=role_def["display_name"],
                description=role_def["description"],
                is_system=False,
            )
            db.add(role)
            await db.flush()
            for perm_name in role_def["permissions"]:
                if perm_name in all_perms:
                    rp = RolePermission(id=uuid.uuid4(), role_id=role.id, permission_id=all_perms[perm_name].id)
                    db.add(rp)
        roles_map[role_name] = role

    await db.flush()

    created_users = {}
    for acct in DEMO_ACCOUNTS:
        user = User(
            id=uuid.uuid4(),
            employee_id=acct["employee_id"],
            username=acct["username"],
            display_name=acct["display_name"],
            email=f"{acct['username']}@demo.local",
            department_id=departments[acct["department"]].id,
            designation=acct["designation"],
            role_id=roles_map[acct["role"]].id,
            password_hash=password_hasher.hash(DEMO_PASSWORD),
        )
        db.add(user)
        created_users[acct["username"]] = user

    await db.flush()

    from models.orm import Document, DocumentPermission, DocumentChunk, DocumentClassification
    import os
    from config import get_settings
    settings = get_settings()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    admin_user = created_users["admin_demo"]
    for doc_def in DEMO_DOCUMENTS:
        doc_id = uuid.uuid4()
        file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.txt")
        with open(file_path, "w") as f:
            f.write(doc_def["content"])

        doc = Document(
            id=doc_id,
            filename=f"{doc_id}.txt",
            original_filename=doc_def["filename"],
            mime_type="application/pdf" if doc_def["filename"].endswith(".pdf") else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_size=len(doc_def["content"]),
            file_path=file_path,
            classification=DocumentClassification(doc_def["classification"]),
            owner_id=admin_user.id,
            department_id=departments["IT"].id if "IT" in departments else list(departments.values())[0].id,
            is_indexed=True,
        )
        db.add(doc)

        # Create chunk for RAG
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_id,
            chunk_index=0,
            content=doc_def["content"],
            page_number=1,
            section="Full Document",
        )
        db.add(chunk)

        # Grant permissions by role
        if not doc_def["allowed_roles"]:
            pass  # public docs accessible via classification check
        else:
            for role_name in doc_def["allowed_roles"]:
                if role_name in roles_map and roles_map[role_name]:
                    perm = DocumentPermission(
                        id=uuid.uuid4(),
                        document_id=doc_id,
                        role_id=roles_map[role_name].id,
                        can_read=True,
                        can_download=True,
                    )
                    db.add(perm)

    await db.commit()

    return {
        "message": "Demo accounts and documents seeded",
        "seeded": True,
        "accounts": [
            {"username": a["username"], "role": a["role"], "display_name": a["display_name"]}
            for a in DEMO_ACCOUNTS
        ],
        "documents": [d["filename"] for d in DEMO_DOCUMENTS],
        "demo_password": DEMO_PASSWORD,
    }
