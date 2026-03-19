# ADR: Event-Driven Policy as Code Architecture for gitpoli

## Status
Proposed

## Context
The `gitpoli` platform implements the Policy as Code principle for managing deployment policies, pull request validations, and release gates. The primary goal is to decouple policy logic from application code, enabling versioning, auditability, and automated validation.

Currently, the codebase and proof of concept (POC) reflect a synchronous, monolithic approach. Events are received, passed directly to the Open Policy Agent (OPA), and logged in a single linear flow. While functional for simple GitHub pull requests, this current state does not scale for advanced, enterprise-grade use cases:
* **Multi-Platform Support:** Receiving events from diverse platforms (GitHub, Azure DevOps, GitLab, etc.) requires a standardized ingestion layer.
* **Complex Policies & Release Gates:** Evaluating rules that depend on external state, such as verifying ITSM ticket approvals (e.g., Jira, ServiceNow) or checking infrastructure status before deploying to production.
* **Asynchronous Execution:** Heavy evaluations and external API calls must not block upstream webhooks or cause timeouts on the platform side.
* **Event Correlation:** Auditing and compliance require linking multiple distinct events over time (e.g., tying a specific PR approval to a deployment artifact and its compliance status).

## Decision
We will transition from the current synchronous POC to an **event-driven, highly decoupled architecture** centered around an asynchronous message broker, a policy orchestrator, and dedicated context enrichment.

---

## 1. Current State Architecture (As-Is / POC)

The current implementation in the repository relies on a synchronous API that tightly couples ingestion, evaluation, and enforcement.

### 1.1 Local Integration Testing (POC)
Uses `smee.io` to proxy webhooks to a local developer machine where a single application handles all logic.

```mermaid
flowchart LR
    GH["GitHub Webhook"] -- "Internet" --> Smee["smee.io proxy"]
    
    subgraph Local_Docker_Compose [Local Developer Machine]
        direction TB
        SmeeClient["Smee Client"]
        App["FastAPI Monolith<br/>(Gateway + Logic + Engine)"]
        OPA["OPA Container"]
        DB[("SQLite / Local DB")]
        
        SmeeClient -- "Forwards payload" --> App
        App -- "Validates & Requests eval" --> OPA
        OPA -- "Returns Decision" --> App
        App -- "Logs event" --> DB
    end
```

### 1.2 Azure Cloud Deployment (POC)
If deployed as-is, the architecture remains synchronous, replacing local containers with managed App Services.

```mermaid
flowchart LR
    GH["GitHub Webhook"] -- "Internet" --> AppService
    
    subgraph Azure_Cloud_POC [Azure Environment - As Is]
        direction TB
        AppService["Azure App Service / Container App<br/>(FastAPI Monolith)"]
        OPA["OPA Container<br/>(Sidecar/Standalone)"]
        Cosmos[("Azure Cosmos DB / PostgreSQL")]
        
        AppService -- "Requests eval" --> OPA
        OPA -- "Returns Decision" --> AppService
        AppService -- "Logs event" --> Cosmos
    end
```

---

## 2. Target Conceptual Architecture (To-Be)

This is the technology-agnostic, high-level component model that dictates the logical flow of the new platform. 

### Architectural Components

1. **Webhook Gateway:** The single, non-blocking entry point that validates incoming webhooks, normalizes diverse payloads into a standardized internal event format (e.g., CloudEvents), and immediately pushes them to the Event Bus.
2. **Message Broker / Event Bus:** The asynchronous messaging backbone that decouples fast ingestion from heavy processing, ensuring system resilience.
3. **Policy Orchestrator:** Consumes normalized events from the bus and coordinates the interaction between the Context Provider, Policy Engine, and Action Dispatcher.
4. **Context Provider:** Responsible for data enrichment. It queries external APIs (ITSM, cloud) or internal databases to build a comprehensive context payload for policies that require external state.
5. **Policy Engine:** A stateless, pure logic execution engine (OPA/Rego) that evaluates the normalized event and enriched context against declarative policy rules.
6. **Action Dispatcher:** Translates the definitive decision from the Policy Engine into platform-specific API calls (e.g., blocking an ADO deployment gate or failing a GitHub PR check).
7. **Event Store & Correlation:** Centralized storage for raw events, enriched contexts, and decisions, providing an immutable audit trail and enabling the correlation of events over time.

```mermaid
flowchart TD
    %% External Entities
    Platforms["External Platforms<br/>(Event Sources & Targets)"]
    ExternalAPIs["External Systems<br/>(ITSM, Cloud, etc.)"]

    %% Ingestion Layer
    Gateway["Webhook Gateway"]
    
    %% Messaging Layer
    EventBus[["Message Broker / Event Bus"]]

    %% Decision Core Layer
    Orchestrator["Policy Orchestrator"]
    ContextEnricher["Context Provider"]
    PolicyEngine["Policy Engine"]
    ActionDispatcher["Action Dispatcher"]

    %% Data and Observability Layer
    EventStore[("Event Store & Correlation")]

    %% --- Relationships ---
    Platforms -- "1. Webhook / Event" --> Gateway
    Gateway -- "2. Normalize & Publish" --> EventBus
    EventBus -- "3. Consume" --> Orchestrator
    Orchestrator -- "4. Request Context" --> ContextEnricher
    ContextEnricher -. "5. Query State" .-> ExternalAPIs
    ContextEnricher -- "6. Return Context" --> Orchestrator
    Orchestrator -- "7. Evaluate (Event + Context)" --> PolicyEngine
    PolicyEngine -- "8. Decision Result" --> Orchestrator
    Orchestrator -- "9. Dispatch Action" --> ActionDispatcher
    ActionDispatcher -- "10. Enforcement API Call" --> Platforms
    EventBus -. "Log Raw Events" .-> EventStore
    Orchestrator -. "Log Decisions" .-> EventStore
```

---

## 3. Target Implementation Architecture (To-Be)

Translating the conceptual model into specific technology stacks for local development and enterprise cloud deployment.

### 3.1 Local / Integration Testing Environment (Docker Compose)
A lightweight containerized setup simulating the distributed cloud architecture for local development.

```mermaid
flowchart TD
    GH["GitHub Webhook"] -- "Internet" --> Smee["smee.io"]
    Smee -- "Forward" --> SmeeClient["Smee Client Container"]

    subgraph Local_Event_Driven_Stack [Local Docker Compose Environment]
        Gateway["Gateway Service<br/>(FastAPI)"]
        EventBus[["Message Broker<br/>(RabbitMQ / Redis)"]]
        
        WorkerCore["Core Workers<br/>(Python Celery / FastStream)"]
        Context["Context Provider<br/>(Python Module)"]
        Engine["Policy Engine<br/>(OPA Container)"]
        Dispatcher["Action Dispatcher<br/>(Python Module)"]
        
        DB[("Event Store<br/>(PostgreSQL Container)")]
    end
    
    MockAPI["Mock ITSM / API<br/>(WireMock / Mountebank)"]

    SmeeClient --> Gateway
    Gateway -- "Publish" --> EventBus
    EventBus -- "Consume" --> WorkerCore
    
    WorkerCore <--> Context
    Context <--> MockAPI
    
    WorkerCore <--> Engine
    WorkerCore --> Dispatcher
    Dispatcher -. "Mock API Call" .-> GH
    
    WorkerCore --> DB
```

### 3.2 Azure Production Environment (Enterprise Stack)
A robust, scalable cloud architecture utilizing managed Azure services and container orchestration.

```mermaid
flowchart TD
    GH["GitHub / ADO Webhooks"] -- "HTTPS" --> Gateway

    subgraph Azure_Enterprise_Stack [Azure Event-Driven Architecture]
        Gateway["API Management / Azure Function<br/>(Webhook Normalizer)"]
        EventBus[["Azure Service Bus<br/>(Topics & Subscriptions)"]]
        
        Orchestrator["Azure Kubernetes Service (AKS) / Container Apps<br/>(Policy Orchestrator)"]
        Context["Context Service<br/>(AKS Pod / Container)"]
        Engine["OPA Engine<br/>(AKS Pod / Container)"]
        Dispatcher["Action Dispatcher<br/>(AKS Pod / Container)"]
        
        DB[("Cosmos DB<br/>(Document Store)")]
        Analytics["Azure Log Analytics<br/>(Event Correlation)"]
    end
    
    ExternalAPIs["ServiceNow / Cloud APIs"]

    Gateway -- "Publish (CloudEvent)" --> EventBus
    EventBus -- "Trigger Worker" --> Orchestrator
    
    Orchestrator <--> Context
    Context <--> ExternalAPIs
    
    Orchestrator <--> Engine
    Orchestrator --> Dispatcher
    Dispatcher -. "Update PR/Gate" .-> GH
    
    Gateway -. "Log Raw" .-> Analytics
    Orchestrator -. "Log Audit" .-> DB
```

---

## Consequences

* **Pros:**
  * **Technology Agnostic:** Core logic is insulated from specific tools; components can be swapped with minimal impact.
  * **Highly Scalable:** Asynchronous processing prevents bottlenecks during high loads or slow external API responses.
  * **Extensible Context:** Easily handles complex policies like Release Gates by plugging new data sources into the Context Provider.
  * **Robust Auditing:** The Event Store provides a single source of truth for compliance reporting and historical event correlation.
* **Cons:**
  * **Increased Architecture Complexity:** Requires deploying and maintaining multiple components (Broker, Store, Orchestrator) compared to a simple synchronous API.
  * **Tracing Difficulty:** Troubleshooting requires robust distributed tracing (e.g., correlation IDs) as requests flow asynchronously through queues.
  * **Eventual Consistency:** External platform updates (like GitHub checks) are not strictly synchronous with the initial webhook trigger.
