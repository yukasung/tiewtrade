from fastapi import FastAPI

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(title="fasttrade API", version="0.1.0")

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
