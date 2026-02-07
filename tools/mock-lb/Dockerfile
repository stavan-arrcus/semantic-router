FROM golang:1 AS builder
WORKDIR /app
COPY main.go .
COPY go.mod .
COPY go.sum .
RUN CGO_ENABLED=0 go build -o mock-lb main.go

FROM scratch
COPY --from=builder /app/mock-lb /mock-lb
ENTRYPOINT ["/mock-lb"]
