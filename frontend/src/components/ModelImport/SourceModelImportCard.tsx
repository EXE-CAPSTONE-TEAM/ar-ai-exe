import { PackageOpen, Upload } from "lucide-react";
import { FormEvent, useState } from "react";

type SourceModelImportCardProps = {
  isBusy: boolean;
  errorMessage: string | null;
  onImport: (file: File) => Promise<void>;
};

/**
 * Import thủ công model 3D gốc cho project KusShoes.
 *
 * Đây là đường tạm thời thay cho luồng scan mobile (chưa làm): khi project trên
 * KusShoes chưa có model canonical, KusStudio cho phép chọn 1 file GLB và đẩy
 * thẳng vào project để web nhìn thấy và duyệt. KusShoes chỉ chấp nhận lần import
 * đầu — model canonical đã có thì không thể thay thế từ desktop.
 */
export function SourceModelImportCard({ isBusy, errorMessage, onImport }: SourceModelImportCardProps) {
  const [file, setFile] = useState<File | null>(null);

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || isBusy) return;
    await onImport(file);
  }

  return (
    <form className="model-import-panel source-model-import" onSubmit={submitImport}>
      <div className="section-heading">
        <PackageOpen size={18} aria-hidden="true" />
        <div>
          <h2>Import model 3D cho project</h2>
          <p className="muted">
            Project này chưa có model gốc. Chọn một file GLB để đưa vào project — web KusShoes sẽ
            thấy ngay model vừa import.
          </p>
        </div>
      </div>

      <div className="import-helper">
        <Upload size={18} aria-hidden="true" />
        <p>Chỉ nhận .glb, tối đa 500 MiB. Mỗi project chỉ import được model gốc một lần.</p>
      </div>

      <label>
        File GLB
        <input
          type="file"
          accept=".glb,model/gltf-binary"
          disabled={isBusy}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </label>

      {errorMessage && <p className="error-text" role="alert">{errorMessage}</p>}

      <button type="submit" className="primary-button" disabled={!file || isBusy}>
        {isBusy ? "Đang import..." : "Import vào project"}
      </button>
    </form>
  );
}
