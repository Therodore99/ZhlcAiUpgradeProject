from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class CalcRequest(BaseModel):
    a: float
    b: float

@app.post("/add")
def add(req: CalcRequest):
    return {
        "result": req.a + req.b
    }