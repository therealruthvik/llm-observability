import random
from locust import HttpUser, between, task

USERS = ["user_alice", "user_bob", "user_carol", "user_dave", "user_eve"]


class LLMObsUser(HttpUser):
    wait_time = between(0.5, 2.0)
    host = "http://localhost:8000"

    @task(8)
    def simulate_single(self):
        self.client.post(
            "/simulate",
            params={"count": random.randint(1, 5), "user_id": random.choice(USERS)},
            name="/simulate",
        )

    @task(2)
    def simulate_burst(self):
        """Spike 15-20 calls at once — triggers cost-spike alert condition."""
        self.client.post(
            "/simulate",
            params={"count": random.randint(15, 20)},
            name="/simulate [burst]",
        )

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")
