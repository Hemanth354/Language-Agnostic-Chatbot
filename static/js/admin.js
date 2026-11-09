// Volunteer & Admin Circulars Handler
document.addEventListener("DOMContentLoaded", () => {
  const uploadForm = document.getElementById("uploadForm");

  if (uploadForm) {
    uploadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(uploadForm);

      const title = formData.get("title");
      const content = formData.get("content");
      const file = formData.get("file");

      if (!content && (!file || !file.name)) {
        alert("Please provide either circular text content or upload a PDF/text file.");
        return;
      }

      const submitBtn = uploadForm.querySelector("button[type='submit']");
      const origText = submitBtn.innerHTML;
      submitBtn.innerHTML = "⏳ Processing & Indexing...";
      submitBtn.disabled = true;

      try {
        const res = await fetch("/api/circulars/upload", {
          method: "POST",
          body: formData
        });

        const data = await res.json();
        if (res.ok) {
          alert("Circular successfully indexed into RAG Vector Store!");
          window.location.reload();
        } else {
          alert("Upload failed: " + (data.error || "Unknown error"));
        }
      } catch (err) {
        console.error("Upload error:", err);
        alert("Server error during upload.");
      } finally {
        submitBtn.innerHTML = origText;
        submitBtn.disabled = false;
      }
    });
  }
});

async function deleteCircular(id) {
  if (!confirm(`Are you sure you want to delete circular #${id}?`)) return;

  try {
    const res = await fetch(`/api/circulars/${id}`, { method: "DELETE" });
    if (res.ok) {
      alert("Circular deleted.");
      window.location.reload();
    } else {
      alert("Error deleting circular.");
    }
  } catch (err) {
    console.error("Delete error:", err);
  }
}

