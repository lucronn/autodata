# Base44 development image for the Go API.
# Ships toolchain + module cache + air only; application source is bind-mounted
# at /src by docker-compose.base44.yml so edits rebuild live.
FROM golang:1.26-bookworm

RUN go install github.com/air-verse/air@latest

WORKDIR /src
COPY apps/api-go/go.mod apps/api-go/go.sum ./apps/api-go/
COPY packages/contracts/go/go.mod packages/contracts/go/contracts.go ./packages/contracts/go/

WORKDIR /src/apps/api-go
RUN go mod download

ENV PATH="/go/bin:${PATH}"
WORKDIR /src/apps/api-go
