/**
 * Verificador dinámico de fortaleza de contraseñas y ayuda interactiva (?)
 * Automatización y Software del Bajío
 */
function initPasswordChecker(inputId, fillId, textId) {
  const pwdInput = document.getElementById(inputId);
  const fillEl = document.getElementById(fillId);
  const textEl = document.getElementById(textId);

  if (!pwdInput || !fillEl || !textEl) return;

  const chkLen = document.getElementById("chk-len");
  const chkNum = document.getElementById("chk-num");
  const chkUpper = document.getElementById("chk-upper");
  const chkLower = document.getElementById("chk-lower");

  function evaluate() {
    const val = pwdInput.value || "";

    const hasLen = val.length >= 8;
    const hasNum = /[0-9]/.test(val);
    const hasUpper = /[A-Z]/.test(val);
    const hasLower = /[a-z]/.test(val);
    const hasSymbol = /[^a-zA-Z0-9]/.test(val);

    // Actualizar checklist visual si existe
    if (chkLen) chkLen.className = hasLen ? "rule-item rule-valid" : "rule-item";
    if (chkNum) chkNum.className = hasNum ? "rule-item rule-valid" : "rule-item";
    if (chkUpper) chkUpper.className = hasUpper ? "rule-item rule-valid" : "rule-item";
    if (chkLower) chkLower.className = hasLower ? "rule-item rule-valid" : "rule-item";

    if (val.length === 0) {
      fillEl.className = "pwd-strength-bar-fill";
      fillEl.style.width = "0%";
      textEl.className = "pwd-strength-label";
      textEl.textContent = "Sin ingresar";
      return;
    }

    let score = 0;
    if (hasLen) score += 1;
    if (val.length >= 12) score += 1;
    if (hasNum) score += 1;
    if (hasUpper) score += 1;
    if (hasLower) score += 1;
    if (hasSymbol) score += 1;

    const allBasic = hasLen && hasNum && hasUpper && hasLower;

    if (!allBasic || score <= 3) {
      fillEl.className = "pwd-strength-bar-fill debil";
      textEl.className = "pwd-strength-label debil";
      textEl.textContent = "Débil";
    } else if (score === 4) {
      fillEl.className = "pwd-strength-bar-fill buena";
      textEl.className = "pwd-strength-label buena";
      textEl.textContent = "Buena";
    } else {
      fillEl.className = "pwd-strength-bar-fill excelente";
      textEl.className = "pwd-strength-label excelente";
      textEl.textContent = "Excelente";
    }
  }

  pwdInput.addEventListener("input", evaluate);
  evaluate();
}

// Soporte para interacción táctil o click en los botones de ayuda (?)
document.addEventListener("DOMContentLoaded", function() {
  document.querySelectorAll(".btn-help-tooltip").forEach(function(btn) {
    btn.addEventListener("click", function(e) {
      e.preventDefault();
      const msg = btn.getAttribute("data-tooltip");
      if (window.innerWidth <= 768 && msg) {
        alert(msg);
      }
    });
  });
});

