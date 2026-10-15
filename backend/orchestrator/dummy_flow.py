import time
from prefect import flow, task
from prefect.client.schemas.schedules import CronSchedule

@task(retries=2, retry_delay_seconds=5)
def scrape_mediamarkt():
    print("MediaMarkt: Scraping gestartet")
    time.sleep(3)
    print("MediaMarkt: Dummy-JSON erstellt")
    return {"retailer": "MediaMarkt", "price_chf": 547.00}


@task
def ingest_mediamarkt(data):
    print(f"Ingestion: {data}")
    time.sleep(2)
    print("Ingestion abgeschlossen")
    return True


@task
def verify_data(success):
    if not success:
        raise RuntimeError("Ingestion fehlgeschlagen")
    print("Verifikation erfolgreich!")


@flow(name="DENG Dummy Pipeline", log_prints=True)
def dummy_pipeline():
    data = scrape_mediamarkt()
    success = ingest_mediamarkt(data)
    verify_data(success)


if __name__ == "__main__":
    dummy_pipeline.serve(
        name="deng-dummy-daily",
        schedule=CronSchedule(
            cron="0 3 * * *",
            timezone="Europe/Zurich"
        ),
        pause_on_shutdown=False,
    )