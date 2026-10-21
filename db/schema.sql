-- 업무 DB DDL (PostgreSQL 16). db/schema.dbml과 같은 구조. 둘을 같이 고친다.
-- 적용: db/reset.sh (스키마 app을 지우고 다시 만든 뒤 시드를 넣는다)

DROP SCHEMA IF EXISTS app CASCADE;
CREATE SCHEMA app;
SET search_path TO app;

-- enum (schemas.common 값과 같다)
CREATE TYPE role AS ENUM ('employee', 'admin', 'system');
CREATE TYPE employee_status AS ENUM ('active', 'on_leave', 'resigned');
CREATE TYPE tool_kind AS ENUM ('ai', 'software');
CREATE TYPE tool_approval_status AS ENUM ('approved', 'under_review', 'denied');
CREATE TYPE data_class AS ENUM ('public', 'internal', 'confidential');
CREATE TYPE billing_type AS ENUM ('seat_flat', 'seat_plus_usage', 'api_usage');
CREATE TYPE task_source AS ENUM ('manual', 'bot');
CREATE TYPE source_kind AS ENUM ('release_notes', 'pricing', 'docs');
CREATE TYPE target_type AS ENUM ('employee', 'team', 'all');
CREATE TYPE suggestion_status AS ENUM ('draft', 'pending_approval', 'sent', 'on_hold');
CREATE TYPE reaction AS ENUM ('useful', 'irrelevant', 'question');
CREATE TYPE unmet_need_status AS ENUM ('open', 'under_review', 'closed');
CREATE TYPE environment AS ENUM ('test', 'prod');
CREATE TYPE seat_status AS ENUM ('assigned', 'unassigned');
CREATE TYPE license_flag AS ENUM ('unused', 'on_leave', 'no_record', 'recent_hire');
CREATE TYPE anomaly_status AS ENUM ('open', 'investigating', 'resolved');
CREATE TYPE plan_type AS ENUM ('seat_assign', 'seat_reclaim', 'model_change', 'budget_review', 'purchase_review');
CREATE TYPE plan_status AS ENUM ('draft', 'pending_approval', 'approved', 'executed', 'failed', 'rejected');
CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high');
CREATE TYPE confirmation_answer AS ENUM ('still_needed', 'return_seat', 'on_leave');
CREATE TYPE savings_kind AS ENUM ('purchase_avoided', 'renewal_reduced', 'billing_reduced', 'projected');
CREATE TYPE job_status AS ENUM ('queued', 'running', 'done', 'failed', 'dead');

-- 조직
CREATE TABLE departments (
  id varchar PRIMARY KEY,
  name varchar NOT NULL,
  parent_id varchar REFERENCES departments(id),
  slack_channel_id varchar,
  suggestions_enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE employees (
  id varchar PRIMARY KEY,
  name varchar NOT NULL,
  email varchar NOT NULL UNIQUE,
  dept_id varchar NOT NULL REFERENCES departments(id),
  role role NOT NULL,
  job_title varchar NOT NULL,
  status employee_status NOT NULL DEFAULT 'active',
  hire_date date,
  slack_user_id varchar UNIQUE,
  password_hash varchar
);

-- 제품·계약·모델
CREATE TABLE tools (
  id varchar PRIMARY KEY,
  kind tool_kind NOT NULL DEFAULT 'ai',
  vendor varchar NOT NULL,
  product varchar NOT NULL,
  category varchar NOT NULL,
  approval_status tool_approval_status NOT NULL,
  allowed_data_class data_class NOT NULL,
  policy_note text
);

CREATE TABLE contracts (
  id varchar PRIMARY KEY,
  tool_id varchar NOT NULL REFERENCES tools(id),
  plan_name varchar NOT NULL,
  billing_type billing_type NOT NULL,
  seats_purchased int NOT NULL DEFAULT 0 CHECK (seats_purchased >= 0),
  seat_price_krw int NOT NULL DEFAULT 0,
  term_start date NOT NULL,
  term_end date NOT NULL CHECK (term_end > term_start),
  mid_term_reduction boolean NOT NULL DEFAULT false
);

CREATE TABLE models (
  id varchar PRIMARY KEY,
  tool_id varchar REFERENCES tools(id),
  vendor varchar NOT NULL,
  name varchar NOT NULL,
  input_usd_per_mtok numeric(10,4) NOT NULL,
  output_usd_per_mtok numeric(10,4) NOT NULL,
  approved boolean NOT NULL DEFAULT true,
  allowed_data_class data_class NOT NULL,
  UNIQUE (vendor, name)
);

CREATE TABLE eval_results (
  id varchar PRIMARY KEY,
  task_type varchar NOT NULL,
  model_id varchar NOT NULL REFERENCES models(id),
  quality_score numeric(5,4) NOT NULL,
  threshold numeric(5,4) NOT NULL,
  passed boolean NOT NULL,
  avg_input_tokens int NOT NULL,
  avg_output_tokens int NOT NULL,
  latency_ms int NOT NULL,
  evaluated_at timestamptz NOT NULL,
  UNIQUE (task_type, model_id)
);

CREATE TABLE registered_tasks (
  id varchar PRIMARY KEY,
  employee_id varchar NOT NULL REFERENCES employees(id),
  title varchar NOT NULL,
  description text NOT NULL,
  frequency varchar NOT NULL,
  tools_used varchar[] NOT NULL DEFAULT '{}',
  source task_source NOT NULL DEFAULT 'manual',
  updated_at timestamptz NOT NULL
);

-- F1 업데이트 기반 제안
CREATE TABLE vendor_sources (
  id varchar PRIMARY KEY,
  vendor varchar NOT NULL,
  url varchar NOT NULL UNIQUE,
  kind source_kind NOT NULL,
  is_candidate boolean NOT NULL DEFAULT false
);

CREATE TABLE vendor_updates (
  id varchar PRIMARY KEY,
  source_id varchar NOT NULL REFERENCES vendor_sources(id),
  vendor varchar NOT NULL,
  published_at timestamptz NOT NULL,
  title varchar NOT NULL,
  summary text NOT NULL,
  url varchar NOT NULL UNIQUE,
  affected_plans varchar[] NOT NULL DEFAULT '{}',
  fetched_at timestamptz NOT NULL
);

CREATE TABLE suggestions (
  id varchar PRIMARY KEY,
  update_id varchar NOT NULL REFERENCES vendor_updates(id),
  target_type target_type NOT NULL,
  target_employee_id varchar REFERENCES employees(id),
  target_dept_id varchar REFERENCES departments(id),
  task_id varchar REFERENCES registered_tasks(id),
  relevance text NOT NULL,
  body text NOT NULL,
  status suggestion_status NOT NULL,
  hold_reason text,
  sent_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON suggestions (target_dept_id, sent_at);

CREATE TABLE feedback (
  id varchar PRIMARY KEY,
  suggestion_id varchar NOT NULL REFERENCES suggestions(id),
  employee_id varchar NOT NULL REFERENCES employees(id),
  reaction reaction NOT NULL,
  created_at timestamptz NOT NULL,
  UNIQUE (suggestion_id, employee_id)
);

CREATE TABLE suggestion_holds (
  id varchar PRIMARY KEY,
  dept_id varchar NOT NULL REFERENCES departments(id),
  tool_category varchar NOT NULL,
  hold_until timestamptz NOT NULL,
  reason varchar NOT NULL,
  UNIQUE (dept_id, tool_category)
);

CREATE TABLE review_runs (
  id varchar PRIMARY KEY,
  update_id varchar NOT NULL REFERENCES vendor_updates(id),
  agent_task_id varchar,
  ran_at timestamptz NOT NULL,
  sent_dept_ids varchar[] NOT NULL DEFAULT '{}',
  held jsonb
);

-- F3 사용량·비용
CREATE TABLE projects (
  id varchar PRIMARY KEY,
  name varchar NOT NULL,
  dept_id varchar NOT NULL REFERENCES departments(id),
  owner_id varchar NOT NULL REFERENCES employees(id),
  purpose text NOT NULL,
  model_id varchar NOT NULL REFERENCES models(id),
  environment environment NOT NULL,
  monthly_budget_krw int NOT NULL
);

CREATE TABLE api_keys (
  id varchar PRIMARY KEY,
  project_id varchar NOT NULL REFERENCES projects(id),
  label varchar NOT NULL,
  vendor_key_ref varchar NOT NULL UNIQUE,
  created_at timestamptz NOT NULL,
  revoked_at timestamptz
);

CREATE TABLE usage_records (
  id bigserial PRIMARY KEY,
  vendor_record_id varchar NOT NULL UNIQUE,
  contract_id varchar NOT NULL REFERENCES contracts(id),
  period_start timestamptz NOT NULL,
  employee_id varchar REFERENCES employees(id),
  project_id varchar REFERENCES projects(id),
  api_key_id varchar REFERENCES api_keys(id),
  model_id varchar REFERENCES models(id),
  input_length_bucket varchar,
  requests int NOT NULL,
  input_tokens bigint NOT NULL,
  output_tokens bigint NOT NULL,
  cost_usd numeric(12,4) NOT NULL,
  fx_rate numeric(10,2) NOT NULL,
  cost_krw int NOT NULL
);
CREATE INDEX ON usage_records (project_id, period_start);
CREATE INDEX ON usage_records (employee_id, period_start);
CREATE INDEX ON usage_records (contract_id, period_start);

CREATE TABLE anomalies (
  id varchar PRIMARY KEY,
  scope_type varchar NOT NULL,
  scope_id varchar NOT NULL,
  rule varchar NOT NULL,
  baseline numeric(14,2) NOT NULL,
  observed numeric(14,2) NOT NULL,
  ratio numeric(8,2) NOT NULL,
  projected_monthly_krw int,
  projected_monthly_usd numeric(12,4),
  status anomaly_status NOT NULL DEFAULT 'open',
  created_at timestamptz NOT NULL
);
CREATE INDEX ON anomalies (scope_type, scope_id, rule, created_at);

-- F4 이용권 · F5 미지원 요청
CREATE TABLE seat_assignments (
  id varchar PRIMARY KEY,
  contract_id varchar NOT NULL REFERENCES contracts(id),
  employee_id varchar NOT NULL REFERENCES employees(id),
  status seat_status NOT NULL,
  assigned_at timestamptz NOT NULL,
  unassigned_at timestamptz,
  last_activity_at timestamptz,
  flag license_flag
);
-- 한 직원은 한 계약에 배정 좌석 하나
CREATE UNIQUE INDEX seat_one_active ON seat_assignments (contract_id, employee_id) WHERE status = 'assigned';

CREATE TABLE unmet_needs (
  id varchar PRIMARY KEY,
  employee_id varchar NOT NULL REFERENCES employees(id),
  dept_id varchar NOT NULL REFERENCES departments(id),
  summary text NOT NULL,
  capability_tag varchar NOT NULL,
  status unmet_need_status NOT NULL DEFAULT 'open',
  created_at timestamptz NOT NULL
);
CREATE INDEX ON unmet_needs (capability_tag);

-- 처리 요청 · 절감 · 감사
CREATE TABLE action_plans (
  id varchar PRIMARY KEY,
  type plan_type NOT NULL,
  risk_level risk_level NOT NULL,
  status plan_status NOT NULL,
  items jsonb NOT NULL,
  rationale text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '[]',
  ai_opinion text,
  requested_by varchar NOT NULL REFERENCES employees(id),
  approver_id varchar REFERENCES employees(id),
  approved_at timestamptz,
  reject_reason text,
  execution_key varchar UNIQUE,
  executed_at timestamptz,
  result jsonb,
  created_at timestamptz NOT NULL
);
CREATE INDEX ON action_plans (status, created_at);

CREATE TABLE confirmations (
  id varchar PRIMARY KEY,
  plan_id varchar NOT NULL REFERENCES action_plans(id),
  employee_id varchar NOT NULL REFERENCES employees(id),
  question text NOT NULL,
  answer confirmation_answer,
  due_at timestamptz NOT NULL,
  answered_at timestamptz,
  UNIQUE (plan_id, employee_id)
);

CREATE TABLE savings_ledger (
  id varchar PRIMARY KEY,
  plan_id varchar NOT NULL REFERENCES action_plans(id),
  kind savings_kind NOT NULL,
  amount_krw int NOT NULL,
  basis text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  id varchar PRIMARY KEY,
  actor_id varchar NOT NULL REFERENCES employees(id),
  actor_role role NOT NULL,
  action varchar NOT NULL,
  target varchar NOT NULL,
  before jsonb,
  after jsonb,
  trace_id varchar,
  created_at timestamptz NOT NULL
);
CREATE INDEX ON audit_log (target, created_at);

-- 운영 (대기열)
CREATE TABLE job_runs (
  id varchar PRIMARY KEY,
  name varchar NOT NULL,
  queue varchar NOT NULL,
  status job_status NOT NULL DEFAULT 'queued',
  attempt int NOT NULL DEFAULT 0,
  idempotency_key varchar NOT NULL UNIQUE,
  payload jsonb,
  last_error text,
  trace_id varchar,
  created_at timestamptz NOT NULL,
  finished_at timestamptz
);
CREATE INDEX ON job_runs (status, created_at);
