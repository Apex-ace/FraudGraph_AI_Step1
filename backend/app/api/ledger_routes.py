"""Protected Step 2 endpoints. Database queries are scoped to the verified owner."""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.security import current_user
from app.schemas.ledger import AccountCreate, AccountOut, ImportBatchOut, TransactionCreate, TransactionOut
from app.services import ledger as svc

router = APIRouter(prefix="/api", tags=["Step 2 · Transactions"])


@router.get("/overview")
def overview(user: dict = Depends(current_user), db: Session = Depends(get_session)):
    return svc.overview(db, svc.get_owner(user))


@router.get("/accounts", response_model=list[AccountOut])
def accounts(user: dict = Depends(current_user), db: Session = Depends(get_session)):
    return svc.get_accounts(db, svc.get_owner(user))


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(value: AccountCreate, user: dict = Depends(current_user), db: Session = Depends(get_session)):
    return svc.create_account(db, svc.get_owner(user), value)


@router.get("/transactions")
def transactions(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                 status: str | None = Query(None, pattern="^(completed|pending|failed)$"),
                 user: dict = Depends(current_user), db: Session = Depends(get_session)):
    return svc.list_transactions(db, svc.get_owner(user), limit, offset, status)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(value: TransactionCreate, user: dict = Depends(current_user), db: Session = Depends(get_session)):
    return svc.create_transaction(db, svc.get_owner(user), value)


@router.post("/transactions/import", response_model=ImportBatchOut, status_code=201)
def import_transactions(file: UploadFile = File(...), user: dict = Depends(current_user), db: Session = Depends(get_session)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(415, detail="Upload a .csv file")
    data = file.file.read(svc.MAX_IMPORT_BYTES + 1)
    parsed = svc.parse_csv(data)
    return svc.import_transactions(db, svc.get_owner(user), file.filename, parsed)


@router.get("/imports", response_model=list[ImportBatchOut])
def imports(user: dict = Depends(current_user), db: Session = Depends(get_session)):
    return svc.list_import_batches(db, svc.get_owner(user))
