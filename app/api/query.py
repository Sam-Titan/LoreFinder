from fastapi import APIRouter, HTTPException
from app.schemas.query_schema import System_Query_Response, UserQuery
from app.services.query_service import run_query_pipeline

router = APIRouter()

@router.post("/", response_model=System_Query_Response)
async def query(payload: UserQuery):
    try:
        result = await run_query_pipeline(payload.doc_id, payload.query)
        return System_Query_Response(
            doc_id=payload.doc_id,
            query=payload.query,
            response=result["answer"],
            references=result["citations"]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError:
        raise HTTPException(status_code=503, detail="Service unavailable. Try again later.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query failed: {str(e)}")