FROM 192.168.56.111:5000/astral-sh/uv:0.9.5@sha256:f459f6f73a8c4ef5d69f4e6fbbdb8af751d6fa40ec34b39a1ab469acd6e289b7 AS uv

FROM 192.168.56.111:5000/ubi9/python-312:1@sha256:19e1e927138b40454858f297884c2c4e2f13f5ba95b3f55faea174d3cbb57067 AS backend
USER 0
RUN dnf remove -y nodejs nodejs-docs nodejs-full-i18n nodejs-libs npm && dnf clean all
USER 1001
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /opt/app-root/src
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    UV_CACHE_DIR=/opt/app-root/src/.cache/uv PATH="/opt/app-root/src/.venv/bin:$PATH"
COPY --chown=1001:0 backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/opt/app-root/src/.cache/uv,uid=1001,gid=0,sharing=locked uv sync --locked --no-dev --no-install-project --python /usr/bin/python3.12
COPY --chown=1001:0 backend/app ./app
RUN --mount=type=cache,target=/opt/app-root/src/.cache/uv,uid=1001,gid=0,sharing=locked uv sync --locked --no-dev --python /usr/bin/python3.12
COPY --chown=1001:0 backend/alembic.ini ./
COPY --chown=1001:0 backend/alembic ./alembic
USER 1001
ENTRYPOINT ["/opt/app-root/src/.venv/bin/python"]
CMD ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]

FROM 192.168.56.111:5000/nginxinc/nginx-unprivileged:1.29.3-alpine@sha256:5aea7cc516b419e3526f47dd1531be31a56a046cfe44754d94f9383e13e2ee99 AS nginx
USER root
RUN apk upgrade --no-cache
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/src/entry.js /usr/share/nginx/html/src/entry.js
COPY frontend/src/native /usr/share/nginx/html/src/native
COPY frontend/src/api /usr/share/nginx/html/src/api
COPY frontend/src/features/catalogs/formHelpers.js /usr/share/nginx/html/src/features/catalogs/formHelpers.js
COPY frontend/src/styles /usr/share/nginx/html/src/styles
USER 101:101
