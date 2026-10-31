This folder contains the application layer (factory, config, models, routes, services,
templates, static assets). It is designed for private commercial publishing workflows.

Boot order:
  create_app()  ->  config  ->  db.init_app  ->  init_redis  ->  register_blueprints
                ->  db.create_all()

Nothing heavy (FAISS, sentence-transformers, Kaggle, ffmpeg) is imported at boot time;
those are loaded lazily so the platform starts even on a minimal install.
