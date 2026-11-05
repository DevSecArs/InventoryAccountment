#!/usr/bin/env python3
"""Проверка одобрения PR через GitHub API."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from review_policy import approved
from acceptance_policy import needs_review


def github(path):
    """Чтение данных GitHub API без прав на запись."""
    token = os.environ["GITHUB_TOKEN"]
    request = Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    try:
        repo = os.environ["GITHUB_REPOSITORY"]
        if not all(
            part and part.replace("-", "").replace("_", "").isalnum()
            for part in repo.split("/")
        ) or len(repo.split("/")) != 2:
            raise ValueError("Некорректное имя репозитория")

        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as file:
            event = json.load(file)

        number = int(event["pull_request"]["number"])
        prefix = f"/repos/{repo}/pulls/{number}"

        pr = github(prefix)
        if pr["state"] != "open":
            raise ValueError("Pull Request не открыт")
        if pr["base"]["ref"] not in {"dev", "main"}:
            raise ValueError("Неподдерживаемая целевая ветка")
        if pr["number"] != number:
            raise ValueError("Номер PR не совпадает")

        # Определяем, затронуты ли критические файлы.
        files = []
        page = 1
        while True:
            batch = github(f"{prefix}/files?per_page=100&page={page}")
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1

        needs_owner = needs_review(files)

        reviews = []
        page = 1
        while True:
            batch = github(f"{prefix}/reviews?per_page=100&page={page}")
            reviews.extend(batch)
            if len(batch) < 100:
                break
            page += 1

        # Повторно проверяем HEAD, чтобы выявить новый push во время проверки.
        current = github(prefix)
        event_sha = event["pull_request"]["head"]["sha"]
        if current["head"]["sha"] != pr["head"]["sha"] or current["head"]["sha"] != event_sha:
            raise ValueError("HEAD изменился после события или во время проверки")

        if not needs_owner:
            print("Критические файлы не изменены.")
            return 0

        if approved(
            reviews,
            current["user"]["login"],
            current["head"]["sha"],
        ):
            print("Одобрение DevSecArs подтверждено.")
            return 0

        print("Нет действительного одобрения DevSecArs.")
        return 1

    except (KeyError, ValueError, HTTPError, URLError, OSError) as error:
        print(f"Проверка не выполнена: {type(error).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
