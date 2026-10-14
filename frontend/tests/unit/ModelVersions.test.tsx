import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../src/i18n";
import { ModelVersionsPanel } from "../../src/features/explorer/ModelVersions";
import type { ModelVersion, ModelVersions } from "../../src/lib/api";

const v = (over: Partial<ModelVersion> = {}): ModelVersion => ({
  version_id: "20261014T155128Z-c7836258",
  trained_utc: "2026-10-14T15:51:28+00:00",
  n_rows: 591372,
  n_stations: 73,
  snapshot_sha256: "c7836258415a",
  conformal_radius_ugm3: 15,
  temporal_mae: 9.92,
  temporal_rmse: 25,
  temporal_r2: 0.579,
  unseen_mae: 10.73,
  baseline_mae: 11.64,
  git_commit: "f465873",
  artifact_present: true,
  ...over,
});

const data = (
  versions: ModelVersion[],
  current: string | null = versions.length > 0 ? versions[versions.length - 1]!.version_id : null,
): ModelVersions => ({ current, versions });

describe("ModelVersionsPanel", () => {
  it("renders nothing when there are no versions yet", () => {
    const { container } = render(
      <I18nextProvider i18n={i18n}>
        <ModelVersionsPanel data={data([])} />
      </I18nextProvider>,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing without data", () => {
    const { container } = render(
      <I18nextProvider i18n={i18n}>
        <ModelVersionsPanel data={null} />
      </I18nextProvider>,
    );
    expect(container.firstChild).toBeNull();
  });

  it("lists every retained version, not just the live one", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <ModelVersionsPanel
          data={data([
            v({ version_id: "v-old", temporal_mae: 12.4 }),
            v({ version_id: "v-new", temporal_mae: 9.92 }),
          ])}
        />
      </I18nextProvider>,
    );
    expect(screen.getByTestId("model-versions")).toBeTruthy();
    expect(screen.getByTestId("model-version-v-old")).toBeTruthy();
    expect(screen.getByTestId("model-version-v-new")).toBeTruthy();
    expect(screen.getByTestId("model-versions").textContent).toMatch(/12\.40/);
    expect(screen.getByTestId("model-versions").textContent).toMatch(/9\.92/);
  });

  it("marks which version is live", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <ModelVersionsPanel
          data={data([v({ version_id: "v-old" }), v({ version_id: "v-new" })], "v-new")}
        />
      </I18nextProvider>,
    );
    expect(screen.getByTestId("model-version-v-new").textContent).toMatch(/live/);
    expect(screen.getByTestId("model-version-v-old").textContent).not.toMatch(/live/);
  });

  // A pruned artifact still has a commit behind it, so hiding it would strand
  // someone trying to work out why a version disappeared.
  it("labels a pruned version instead of hiding it", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <ModelVersionsPanel
          data={data([v({ version_id: "v-gone", artifact_present: false, git_commit: "abc1234" })])}
        />
      </I18nextProvider>,
    );
    const row = screen.getByTestId("model-version-v-gone");
    expect(row.textContent).toMatch(/pruned/);
  });

  it("shows unseen-station accuracy next to temporal so the weak case is visible", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <ModelVersionsPanel data={data([v({ unseen_mae: 10.73 })])} />
      </I18nextProvider>,
    );
    expect(screen.getByTestId("model-versions").textContent).toMatch(/10\.73/);
  });

  it("does not print NaN when a metric is absent", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <ModelVersionsPanel
          data={data([v({ temporal_mae: null, temporal_rmse: null, temporal_r2: null, unseen_mae: null })])}
        />
      </I18nextProvider>,
    );
    const text = screen.getByTestId("model-versions").textContent ?? "";
    expect(text).not.toMatch(/NaN|undefined/);
  });

  it("explains what the table is for", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <ModelVersionsPanel data={data([v()])} />
      </I18nextProvider>,
    );
    expect(screen.getByTestId("model-versions").textContent).toMatch(/MAE/);
  });
});
