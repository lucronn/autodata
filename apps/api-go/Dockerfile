FROM golang:1.26-bookworm AS build

WORKDIR /src
COPY apps/api-go/go.mod ./apps/api-go/
COPY apps/api-go/*.go ./apps/api-go/
WORKDIR /src/apps/api-go
RUN CGO_ENABLED=0 go build -trimpath -o /out/autodata-api .

FROM golang:1.26-bookworm
COPY --from=build /out/autodata-api /usr/local/bin/autodata-api
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/autodata-api"]
