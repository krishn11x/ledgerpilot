import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "../lib/api";

const REQUIRED_FILES = [
  { key: "orders", label: "Orders", accept: ".csv" },
  { key: "gateway_txns", label: "Gateway transactions", accept: ".csv" },
  { key: "payouts", label: "Payouts", accept: ".csv" },
  { key: "bank_txns", label: "Bank statement", accept: ".csv" },
] as const;

type UploadMode = "demo" | "upload";
type UploadMap = Record<(typeof REQUIRED_FILES)[number]["key"], File | null>;

function formatFileStatus(file: File | null) {
  if (!file) return "No file selected";
  return `✓ ${file.name} selected`;
}

type ScenarioItem = {
  name: string;
  description: string;
  seed: number;
  order_count: number;
  period_days: number;
};

export default function Workflow() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<UploadMode>("demo");
  const [selectedScenario, setSelectedScenario] = useState("smoke");
  const [uploadFiles, setUploadFiles] = useState<UploadMap>({
    orders: null,
    gateway_txns: null,
    payouts: null,
    bank_txns: null,
  });
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [ingestProgress, setIngestProgress] = useState<number>(0);
  const [ingestMessage, setIngestMessage] = useState("Waiting to start");
  const [uploadState, setUploadState] = useState<"idle" | "valid" | "uploading" | "uploaded">("idle");

  const scenariosQuery = useQuery({
    queryKey: ["scenarios"],
    queryFn: () => api.get<{ items: ScenarioItem[]; total: number }>("/scenarios"),
  });

  const generateScenario = useMutation({
    mutationFn: (scenario: string) =>
      api.post<{ paths: Record<string, string>; ground_truth: number }>("/scenarios/generate", {
        scenario,
      }),
  });

  const startRun = useMutation({
    mutationFn: (scenario: string) =>
      api.post<{ run_id: string; scenario: string; counts: Record<string, number>; status: string }>(
        "/runs",
        { scenario },
      ),
  });

  const validation = useMemo(() => {
    const missing: string[] = [];
    const selected: string[] = [];

    for (const entry of REQUIRED_FILES) {
      const file = uploadFiles[entry.key];
      if (!file) {
        missing.push(entry.label);
        continue;
      }
      if (!file.name.toLowerCase().endsWith(".csv")) {
        missing.push(`${entry.label} must be a CSV file`);
        continue;
      }
      selected.push(file.name);
    }

    return {
      ok: missing.length === 0 && selected.length === REQUIRED_FILES.length,
      missing,
      selected,
    };
  }, [uploadFiles]);

  const handleFileChange = (key: (typeof REQUIRED_FILES)[number]["key"], file: File | null) => {
    setUploadError(null);
    setUploadFiles((prev) => ({ ...prev, [key]: file }));
  };

  const handleDemoRun = async () => {
    const scenario = selectedScenario || "smoke";
    try {
      await generateScenario.mutateAsync(scenario);
      const run = await startRun.mutateAsync(scenario);
      navigate(`/results/${run.run_id}`);
    } catch (error) {
      console.error("demo workflow failed", error);
    }
  };

  const handleUploadValidation = () => {
    if (!validation.ok) {
      setUploadError(
        validation.missing.length
          ? `Missing or invalid files: ${validation.missing.join(", ")}`
          : "Please choose all four required files before continuing.",
      );
      setUploadState("idle");
      return;
    }

    setUploadError(null);
    setUploadState("valid");
    setIngestProgress(0);
    setIngestMessage("Validating files");

    const steps = [
      "Validating file headers",
      "Checking required columns",
      "Checking row counts",
      "Preparing ingestion",
      "Ready for reconciliation",
    ];

    let stepIndex = 0;
    const timer = window.setInterval(() => {
      setIngestProgress((prev) => {
        const next = Math.min(prev + 20, 100);
        if (next >= 100) {
          setIngestMessage("Validation complete");
          setUploadState("uploaded");
          window.clearInterval(timer);
        } else {
          setIngestMessage(steps[stepIndex] ?? "Validating files");
          stepIndex += 1;
        }
        return next;
      });
    }, 350);
  };

  const uploadFilesMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      for (const entry of REQUIRED_FILES) {
        const file = uploadFiles[entry.key];
        if (!file) {
          throw new Error(`Missing required file: ${entry.label}`);
        }
        formData.append(entry.key, file, file.name);
      }

      const payload = await api.post<{ run_id: string; status: string; counts: Record<string, number> }>(
        "/upload",
        formData,
      );
      return payload;
    },
  });

  const handleUploadAndReconcile = async () => {
    if (!validation.ok) {
      setUploadError(
        validation.missing.length
          ? `Missing or invalid files: ${validation.missing.join(", ")}`
          : "Please choose all four required files before continuing.",
      );
      return;
    }

    setUploadState("uploading");
    setUploadError(null);
    setIngestProgress(5);
    setIngestMessage("Uploading files to the backend");

    try {
      const result = await uploadFilesMutation.mutateAsync();
      setIngestProgress(100);
      setIngestMessage("Upload complete");
      navigate(`/results/${result.run_id}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Upload failed.";
      setUploadError(message);
      setUploadState("valid");
      setIngestProgress(0);
      setIngestMessage("Upload failed");
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header className="space-y-4">
        <p className="text-xs uppercase tracking-[0.2em] text-accent">Data in → Reconciliation → Result</p>
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">New reconciliation</h1>
            <p className="mt-2 max-w-2xl text-sm text-ink-muted">
              Start from a real dataset or a demo scenario. The app guides the workflow to run,
              review exceptions, and measure the outcome.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/exceptions")}
            className="border border-border-subtle bg-surface px-4 py-2 text-sm text-ink hover:bg-surface-raised"
          >
            Review exceptions
          </button>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <button
          type="button"
          onClick={() => setMode("demo")}
          className={`border p-5 text-left transition ${
            mode === "demo"
              ? "border-accent bg-surface-raised"
              : "border-border-subtle bg-surface hover:bg-surface-raised/70"
          }`}
        >
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Option A</p>
          <h2 className="mt-3 text-xl font-semibold">Try a demo scenario</h2>
          <p className="mt-2 text-sm text-ink-muted">
            Use the existing synthetic scenarios already supported by the backend.
          </p>
        </button>

        <button
          type="button"
          onClick={() => setMode("upload")}
          className={`border p-5 text-left transition ${
            mode === "upload"
              ? "border-accent bg-surface-raised"
              : "border-border-subtle bg-surface hover:bg-surface-raised/70"
          }`}
        >
          <p className="text-xs uppercase tracking-[0.2em] text-accent">Option B</p>
          <h2 className="mt-3 text-xl font-semibold">Upload real files</h2>
          <p className="mt-2 text-sm text-ink-muted">
            Select order, gateway, payout, and bank files for a manual validation pass.
          </p>
        </button>
      </section>

      {mode === "demo" ? (
        <section className="border border-border-subtle bg-surface p-5">
          <div className="flex flex-col gap-5 md:flex-row md:items-end">
            <div className="flex-1">
              <label htmlFor="scenario" className="text-xs uppercase tracking-[0.2em] text-ink-faint">
                Scenario
              </label>
              <select
                id="scenario"
                value={selectedScenario}
                onChange={(event) => setSelectedScenario(event.target.value)}
                className="mt-2 w-full border border-border-subtle bg-canvas px-3 py-2 text-sm text-ink outline-none"
              >
                {scenariosQuery.data?.items.map((scenario) => (
                  <option key={scenario.name} value={scenario.name}>
                    {scenario.name}
                  </option>
                )) ?? <option value="smoke">smoke</option>}
              </select>
            </div>

            <button
              type="button"
              onClick={handleDemoRun}
              disabled={generateScenario.isPending || startRun.isPending}
              className="bg-accent px-5 py-2.5 text-sm font-medium text-canvas disabled:cursor-not-allowed disabled:opacity-60"
            >
              {startRun.isPending ? "Running reconciliation…" : "Run reconciliation"}
            </button>
          </div>

          <div className="mt-5 rounded border border-border-subtle bg-canvas p-4 text-sm text-ink-muted">
            <p className="font-medium text-ink">Selected scenario</p>
            <p className="mt-2">
              {scenariosQuery.data?.items.find((item) => item.name === selectedScenario)?.description ??
                "Synthetic dataset for demo validation."}
            </p>
          </div>
        </section>
      ) : (
        <section className="border border-border-subtle bg-surface p-5">
          <div className="space-y-4">
            {REQUIRED_FILES.map((entry) => (
              <div key={entry.key} className="border border-border-subtle bg-canvas p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-ink-faint">{entry.label}</p>
                    <p className="mt-2 text-xs text-ink-muted">{formatFileStatus(uploadFiles[entry.key])}</p>
                  </div>

                  <label className="inline-flex cursor-pointer items-center justify-center border border-border-subtle bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-surface-raised">
                    <span>Choose {entry.label} File</span>
                    <input
                      type="file"
                      accept={entry.accept}
                      className="hidden"
                      onChange={(event) => handleFileChange(entry.key, event.target.files?.[0] ?? null)}
                    />
                  </label>
                </div>

                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="text-xs text-ink-faint">{uploadFiles[entry.key] ? "Ready to upload" : "No file selected"}</span>
                  {uploadFiles[entry.key] ? (
                    <button
                      type="button"
                      onClick={() => handleFileChange(entry.key, null)}
                      className="text-xs text-sev-high underline underline-offset-2"
                    >
                      Remove
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          {uploadError ? <p className="mt-4 text-sm text-sev-high">{uploadError}</p> : null}

          <div className="mt-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex-1">
              <p className="text-xs uppercase tracking-[0.2em] text-ink-faint">Step 1 — Choose data</p>
              <p className="mt-2 text-sm text-ink-muted">
                {validation.ok
                  ? `All ${REQUIRED_FILES.length} files are ready for intake.`
                  : `Selected ${validation.selected.length} of ${REQUIRED_FILES.length} files.`}
              </p>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleUploadValidation}
                className="border border-border-subtle bg-surface px-4 py-2 text-sm hover:bg-surface-raised"
              >
                Validate Files
              </button>
              <button
                type="button"
                onClick={handleUploadAndReconcile}
                disabled={!validation.ok || uploadFilesMutation.isPending}
                className="bg-accent px-4 py-2 text-sm font-medium text-canvas disabled:cursor-not-allowed disabled:opacity-60"
              >
                {uploadFilesMutation.isPending ? "Uploading…" : "Ingest Data"}
              </button>
            </div>
          </div>

          <div className="mt-6 rounded border border-border-subtle bg-canvas p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-ink-muted">Step 2 — Validate / Ingest</span>
              <span className="money">{ingestProgress}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden border border-border-subtle bg-surface">
              <div className="h-full bg-accent" style={{ width: `${ingestProgress}%` }} />
            </div>
            <p className="mt-3 text-sm text-ink-muted">{ingestMessage}</p>
            {uploadError ? <p className="mt-3 text-sm text-sev-high">{uploadError}</p> : null}
            {uploadState === "uploaded" || uploadFilesMutation.isSuccess ? (
              <div className="mt-4 border border-border-subtle bg-surface p-3 text-sm text-ink-muted">
                <p className="font-medium text-ink">Ready for reconciliation</p>
                <p className="mt-2">The uploaded files have passed validation and the next step is to reconcile.</p>
              </div>
            ) : null}
          </div>
        </section>
      )}
    </div>
  );
}
