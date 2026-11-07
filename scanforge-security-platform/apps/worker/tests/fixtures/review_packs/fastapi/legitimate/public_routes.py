from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter()


@app.get("/health")
def health():
    return {"status": "ok"}


@router.post("/login")
async def login(credentials: dict):
    return {"token": "issued-elsewhere"}
