"""The documented frontend flows use the actual mounted API."""

from app.main import app


def test_sprint2_openapi_documents_owned_routes_and_errors():
    spec = app.openapi()
    paths = spec["paths"]
    routes = [
        ("post", "/api/upload", "201", ("409", "413", "415", "422", "503")),
        ("get", "/api/workspaces/{id}/analysis", "200", ("404", "409", "503")),
        (
            "post",
            "/api/workspaces/{workspace_id}/summary",
            "200",
            ("409", "429", "502", "503"),
        ),
        ("get", "/api/upload-attempts", "200", ("422", "503")),
        ("get", "/api/upload-attempts/{attempt_id}", "200", ("404", "422", "503")),
        (
            "post",
            "/api/upload-attempts/{attempt_id}/recover",
            "200",
            ("404", "409", "422", "503"),
        ),
    ]
    for method, path, success, errors in routes:
        operation = paths[path][method]
        assert operation["security"] == [{"HTTPBearer": []}]
        for status in (success, "401", *errors):
            assert "application/json" in operation["responses"][status]["content"]

    recover = paths["/api/upload-attempts/{attempt_id}/recover"]["post"]
    assert "201" not in recover["responses"]
    body = recover["requestBody"]
    schemas = spec["components"]["schemas"]
    assert body["required"]
    schema_ref = body["content"]["application/json"]["schema"]["$ref"]
    request = schemas[schema_ref.rsplit("/", 1)[1]]
    assert request["properties"] == {}
    assert request["additionalProperties"] is False

    detail = schemas["UploadErrorDetail"]
    assert set(detail["required"]) == {"code", "message"}
    assert set(detail["properties"]) == {"code", "message", "attempt_id"}
