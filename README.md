# Distributed News Crawler

A scalable distributed system for crawling, collecting, and serving news articles from multiple online sources.

## Overview

Distributed News Crawler is designed to fetch news content from various websites, process it, and expose the data through an API and frontend interface. The system is built with scalability in mind, allowing multiple crawler instances to run in parallel.

The project is structured into separate components for crawling, data handling, backend endpoints, and frontend display.

## Features

* Distributed web crawling architecture
* Parallel crawling for improved performance
* News article extraction and structured storage
* REST API for accessing collected data
* Frontend interface for browsing news

## Project Structure

```
crawler/     # Crawling logic and worker processes
data/        # Data storage and processing
endpoints/   # Backend API routes and services
frontend/    # User interface
```

## How It Works

1. Crawler workers fetch news articles from configured sources.
2. Extracted content is cleaned and stored.
3. Backend endpoints expose the stored data.
4. The frontend consumes the API to display news articles.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/AbirAbidi/distributed-news-crawler.git
cd distributed-news-crawler
```

### 2. Install dependencies

Install dependencies for each component (crawler, backend, frontend) according to their respective requirements files or package configurations.

### 3. Run the system

Start the backend service, launch crawler workers, and run the frontend application.

## Use Cases

* News aggregation platforms
* Content monitoring systems
* Data collection for NLP or analytics
* Research on media trends


