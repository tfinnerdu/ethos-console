'use strict';

/* Shared confirmation dialog for every state-changing action in the console.
 *
 * window.confirmAction(opts) -> Promise<boolean>
 *   opts.title         dialog title
 *   opts.message       plain-text body (rendered as textContent, never HTML)
 *   opts.confirmLabel  confirm button label (default "Confirm")
 *   opts.danger        true -> red confirm button (deletes / destructive ops)
 *   opts.requireText   if set, the user must type this exact string to unlock
 *                      the confirm button (type-to-confirm for caustic actions)
 *
 * Resolves true if the user confirms, false if they cancel or dismiss.
 */
(function () {
  function ensureModal() {
    if (document.getElementById('confirm-modal')) return;
    var html =
      '<div class="modal fade" id="confirm-modal" tabindex="-1" aria-hidden="true">' +
      '  <div class="modal-dialog modal-dialog-centered">' +
      '    <div class="modal-content">' +
      '      <div class="modal-header py-2">' +
      '        <h6 class="modal-title" id="confirm-modal-title">Confirm</h6>' +
      '        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>' +
      '      </div>' +
      '      <div class="modal-body">' +
      '        <div id="confirm-modal-message" class="small" style="white-space:pre-wrap"></div>' +
      '        <div id="confirm-modal-type-wrap" class="mt-3" style="display:none">' +
      '          <label class="form-label small mb-1">Type <code id="confirm-modal-type-token"></code> to confirm:</label>' +
      '          <input type="text" class="form-control form-control-sm font-monospace" id="confirm-modal-type-input" autocomplete="off" spellcheck="false" />' +
      '        </div>' +
      '      </div>' +
      '      <div class="modal-footer py-2">' +
      '        <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>' +
      '        <button type="button" class="btn btn-sm" id="confirm-modal-ok">Confirm</button>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '</div>';
    var wrap = document.createElement('div');
    wrap.innerHTML = html;
    document.body.appendChild(wrap.firstElementChild);
  }

  window.confirmAction = function (opts) {
    opts = opts || {};
    ensureModal();

    return new Promise(function (resolve) {
      var modalEl = document.getElementById('confirm-modal');
      var titleEl = document.getElementById('confirm-modal-title');
      var msgEl = document.getElementById('confirm-modal-message');
      var okBtn = document.getElementById('confirm-modal-ok');
      var typeWrap = document.getElementById('confirm-modal-type-wrap');
      var typeToken = document.getElementById('confirm-modal-type-token');
      var typeInput = document.getElementById('confirm-modal-type-input');

      titleEl.textContent = opts.title || 'Confirm';
      msgEl.textContent = opts.message || 'Are you sure?';
      okBtn.textContent = opts.confirmLabel || 'Confirm';
      okBtn.className = 'btn btn-sm ' + (opts.danger ? 'btn-danger' : 'btn-doane');

      var requireText = (opts.requireText || '').trim();
      var settled = false;
      var modal = bootstrap.Modal.getOrCreateInstance(modalEl);

      function matches() {
        return !requireText || typeInput.value.trim() === requireText;
      }
      function cleanup() {
        okBtn.removeEventListener('click', onOk);
        typeInput.removeEventListener('input', onType);
        typeInput.removeEventListener('keydown', onKey);
        modalEl.removeEventListener('hidden.bs.modal', onHide);
      }
      function finish(result) {
        if (settled) return;
        settled = true;
        cleanup();
        resolve(result);
      }
      function onOk() {
        if (!matches()) return;
        finish(true);
        modal.hide();
      }
      function onType() {
        okBtn.disabled = !matches();
      }
      function onKey(e) {
        if (e.key === 'Enter') { e.preventDefault(); onOk(); }
      }
      function onHide() {
        finish(false);
      }

      if (requireText) {
        typeWrap.style.display = '';
        typeToken.textContent = requireText;
        typeInput.value = '';
        okBtn.disabled = true;
        typeInput.addEventListener('input', onType);
        typeInput.addEventListener('keydown', onKey);
      } else {
        typeWrap.style.display = 'none';
        okBtn.disabled = false;
      }

      okBtn.addEventListener('click', onOk);
      modalEl.addEventListener('hidden.bs.modal', onHide);

      modal.show();
      if (requireText) {
        setTimeout(function () { typeInput.focus(); }, 300);
      }
    });
  };
}());
