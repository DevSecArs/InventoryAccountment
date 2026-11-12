FROM 192.168.56.111:5000/library/golang:1.27.4-bookworm@sha256:4fa7c968ba93f1635670522dbb01a2c78150443e1385746924566079f36570ea AS gosu-builder

WORKDIR /src
ENV CGO_ENABLED=0

COPY docker/gosu/go.mod docker/gosu/go.sum ./
RUN go mod download

COPY docker/gosu/*.go ./
RUN go build -buildvcs=false -trimpath -ldflags="-s -w" -o /gosu . \
    && /gosu --version

FROM 192.168.56.111:5000/library/postgres:17.11-bookworm@sha256:665dc7b37ac52a17e298511414c21d23ffa4e6a6ef6225b3e5d59c7afb35e994

COPY --from=gosu-builder --chmod=0755 /gosu /usr/local/bin/gosu
