.PHONY: up
up:
	docker-compose up --build --scale node_api=2

.PHONY: down
down:
	docker-compose down