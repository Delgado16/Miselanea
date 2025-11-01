// Funciones globales para el sistema

// Importación de Bootstrap
const bootstrap = window.bootstrap

// Auto-cerrar alertas después de 5 segundos
document.addEventListener("DOMContentLoaded", () => {
  const alerts = document.querySelectorAll(".alert")
  alerts.forEach((alert) => {
    setTimeout(() => {
      const bsAlert = new bootstrap.Alert(alert)
      bsAlert.close()
    }, 5000)
  })
})

// Confirmar eliminación
function confirmarEliminacion(mensaje = "¿Estás seguro de eliminar este elemento?") {
  return confirm(mensaje)
}

// Formatear números como moneda
function formatearMoneda(valor) {
  return new Intl.NumberFormat("es-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(valor)
}

// Validar formularios
function validarFormulario(formId) {
  const form = document.getElementById(formId)
  if (!form.checkValidity()) {
    form.classList.add("was-validated")
    return false
  }
  return true
}

// Buscar en tablas
function buscarEnTabla(inputId, tableId) {
  const input = document.getElementById(inputId)
  const filter = input.value.toLowerCase()
  const table = document.getElementById(tableId)
  const rows = table.getElementsByTagName("tr")

  for (let i = 1; i < rows.length; i++) {
    const row = rows[i]
    const cells = row.getElementsByTagName("td")
    let found = false

    for (let j = 0; j < cells.length; j++) {
      const cell = cells[j]
      if (cell.textContent.toLowerCase().indexOf(filter) > -1) {
        found = true
        break
      }
    }

    row.style.display = found ? "" : "none"
  }
}

// Mostrar/ocultar spinner de carga
function toggleSpinner(show = true) {
  const spinner = document.getElementById("loadingSpinner")
  if (spinner) {
    spinner.style.display = show ? "block" : "none"
  }
}

// Notificación toast
function mostrarToast(mensaje, tipo = "info") {
  const toastContainer = document.getElementById("toastContainer")
  if (!toastContainer) {
    const container = document.createElement("div")
    container.id = "toastContainer"
    container.className = "toast-container position-fixed top-0 end-0 p-3"
    document.body.appendChild(container)
  }

  const toastHtml = `
        <div class="toast align-items-center text-white bg-${tipo} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">${mensaje}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `

  const toastElement = document.createElement("div")
  toastElement.innerHTML = toastHtml
  document.getElementById("toastContainer").appendChild(toastElement.firstElementChild)

  const toast = new bootstrap.Toast(toastElement.firstElementChild)
  toast.show()
}
