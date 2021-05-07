NODES ?= 2

.PHONY: up
up:
	docker-compose up --build --scale node=$(NODES)

.PHONY: down
down:
	docker-compose down