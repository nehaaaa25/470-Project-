document.addEventListener("DOMContentLoaded", () => {
  // Register page: show only the extra fields for the chosen account type.
  const roleSelect = document.getElementById("role");
  if (roleSelect) {
    const update = () => {
      document.querySelectorAll(".role-fields").forEach((block) => {
        const active = block.dataset.role === roleSelect.value;
        block.hidden = !active;
        block.disabled = !active; // disabled fieldsets are not submitted
      });
    };
    roleSelect.addEventListener("change", update);
    update();
  }

  // Any <form data-confirm="..."> asks before submitting (used for delete buttons).
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  // Material form: non-recyclable materials earn no points.
  const recyclable = document.getElementById("is_recyclable");
  const points = document.getElementById("points_per_kg");
  if (recyclable && points) {
    const sync = () => {
      if (!recyclable.checked) points.value = "0";
      points.readOnly = !recyclable.checked;
    };
    recyclable.addEventListener("change", sync);
    sync();
  }
});
