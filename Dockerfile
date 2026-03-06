FROM mambaorg/micromamba:1.5.8

WORKDIR /app

COPY environment.yml /tmp/environment.yml
RUN micromamba env create -f /tmp/environment.yml && micromamba clean --all --yes

SHELL ["micromamba", "run", "-n", "civicview", "/bin/bash", "-c"]

COPY . /app

ENV DJANGO_SETTINGS_MODULE=civicview_project.settings \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["micromamba", "run", "-n", "civicview", "gunicorn", "civicview_project.wsgi:application", "--bind", "0.0.0.0:8000"]


