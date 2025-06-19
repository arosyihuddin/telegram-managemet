from fastapi import FastAPI, Request, HTTPException, status


# Authentication dependency
def get_current_user(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return request.session.get("username")
