.PHONY: up
up:
	docker-compose up --build --scale node=3

.PHONY: down
down:
	docker-compose down