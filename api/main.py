from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.post("/upload")
def upload_video():
    return {}

@app.get("/process")
def process_video():
    return {}

