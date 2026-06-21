const form = document.querySelector('#clip-form');
const tabs = [...document.querySelectorAll('.mode-tab')];
const panels = { upload: document.querySelector('#upload-panel'), url: document.querySelector('#url-panel') };
const fileInput = document.querySelector('#video-input');
const dropzone = document.querySelector('#dropzone');
const fileTitle = document.querySelector('#file-title');
const fileDetail = document.querySelector('#file-detail');
const errorBox = document.querySelector('#form-error');
const submitButton = document.querySelector('#submit-button');
const progressSection = document.querySelector('#progress-section');
const progressTitle = document.querySelector('#progress-title');
const progressMessage = document.querySelector('#progress-message');
const resultsSection = document.querySelector('#results-section');
const resultsGrid = document.querySelector('#results-grid');
let activeMode = 'upload';

tabs.forEach(tab => tab.addEventListener('click', () => {
  activeMode = tab.dataset.mode;
  tabs.forEach(item => {
    const active = item === tab;
    item.classList.toggle('active', active);
    item.setAttribute('aria-selected', String(active));
  });
  Object.entries(panels).forEach(([name, panel]) => panel.classList.toggle('active', name === activeMode));
  hideError();
}));

function showFile(file) {
  if (!file) return;
  fileTitle.textContent = file.name;
  fileDetail.textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB · Ready to process`;
  dropzone.classList.add('has-file');
}
fileInput.addEventListener('change', () => showFile(fileInput.files[0]));
['dragenter', 'dragover'].forEach(name => dropzone.addEventListener(name, event => {
  event.preventDefault(); dropzone.classList.add('dragging');
}));
['dragleave', 'drop'].forEach(name => dropzone.addEventListener(name, event => {
  event.preventDefault(); dropzone.classList.remove('dragging');
}));
dropzone.addEventListener('drop', event => {
  const file = event.dataTransfer.files[0];
  if (!file) return;
  const transfer = new DataTransfer(); transfer.items.add(file); fileInput.files = transfer.files; showFile(file);
});

function showError(message) { errorBox.textContent = message; errorBox.hidden = false; }
function hideError() { errorBox.hidden = true; errorBox.textContent = ''; }

form.addEventListener('submit', async event => {
  event.preventDefault(); hideError();
  if (activeMode === 'upload' && !fileInput.files.length) return showError('Choose a video to continue.');
  if (activeMode === 'url' && !document.querySelector('#url-input').value.trim()) return showError('Paste a video URL to continue.');

  const data = new FormData();
  data.append('max_clips', document.querySelector('#max-clips').value);
  if (activeMode === 'upload') data.append('video', fileInput.files[0]);
  else data.append('url', document.querySelector('#url-input').value.trim());
  submitButton.disabled = true;
  submitButton.querySelector('span').textContent = 'Uploading…';
  try {
    const response = await fetch('/api/jobs', { method: 'POST', body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Could not start the job.');
    submitButton.querySelector('span').textContent = 'Processing…';
    progressSection.hidden = false;
    progressSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
    await pollJob(payload.job_id);
  } catch (error) {
    showError(error.message); submitButton.disabled = false; submitButton.querySelector('span').textContent = 'Create my clips';
  }
});

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.error || 'Unable to read job status.');
    const stageTitles = {
      download: 'Getting your video…', transcribe: 'Transcribing locally…',
      analyze: 'Finding the best moments…', export: 'Rendering vertical clips…',
      finalize: 'Finishing up…'
    };
    progressTitle.textContent = job.status === 'queued' ? 'Your video is queued…' : (stageTitles[job.stage] || 'Creating your clips…');
    progressMessage.textContent = job.message;
    if (job.status === 'completed') return renderResults(job.result);
    if (job.status === 'failed') throw new Error(job.message);
    setTimeout(() => pollJob(jobId), 1800);
  } catch (error) {
    progressSection.hidden = true; showError(error.message); submitButton.disabled = false;
    submitButton.querySelector('span').textContent = 'Create my clips';
  }
}

function renderResults(result) {
  progressSection.hidden = true;
  resultsGrid.innerHTML = result.clips.map((clip, index) => `
    <article class="clip-card">
      <video class="clip-video" controls preload="metadata" src="${clip.video_url}"></video>
      <div class="clip-content">
        <span class="score">✦ VIRAL SCORE ${clip.viral_score}/10</span>
        <h3>${escapeHtml(clip.title)}</h3>
        <p>${escapeHtml(clip.caption)}</p>
        <div class="clip-actions">
          <a href="${clip.video_url}" download>Download MP4</a>
          <a href="${clip.subtitle_url}" download>Get subtitles</a>
        </div>
      </div>
    </article>`).join('');
  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  submitButton.disabled = false; submitButton.querySelector('span').textContent = 'Create my clips';
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}
document.querySelector('#new-job').addEventListener('click', () => {
  resultsSection.hidden = true; form.reset(); dropzone.classList.remove('has-file');
  fileTitle.textContent = 'Drop your video here'; fileDetail.textContent = 'or click to browse your files';
  document.querySelector('.workspace').scrollIntoView({ behavior: 'smooth' });
});
