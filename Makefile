.PHONY: test build run deb

test:
	cd go && go test ./...

build:
	mkdir -p dist
	cd go && CGO_ENABLED=0 go build -ldflags="-s -w" -o ../dist/lightwrite ./cmd/lightwrite

run:
	cd go && go run ./cmd/lightwrite

deb:
	bash scripts/build-deb.sh
