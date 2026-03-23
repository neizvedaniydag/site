import { PoseLandmarker, FaceLandmarker, FilesetResolver, DrawingUtils } from "@mediapipe/tasks-vision";
import { squat } from './exercises/squat.js';
import { pushup } from './exercises/pushup.js';
import { neck } from './exercises/neck.js';
import { situp } from './exercises/situp.js';
import { plank } from './exercises/plank.js';
import { mountain } from './exercises/mountain.js';

console.log('=== MediaPipe загружен ===');

const EXERCISES = {
    squat,
    pushup,
    neck,
    situp,
    plank,
    mountain
};

var faceLandmarker, poseLandmarker;
var video = document.getElementById('webcam');
var canvas = document.getElementById('canvas');
var ctx = canvas.getContext('2d');
var running = false, recording = false;

var currentExercise = null;
var exerciseState = {};
var counter = 0, correct = 0, incorrect = 0, errorLog = [];
var hintsEnabled = true;

// Для планки нужен таймер времени, потому что планка измеряется в СЕКУНДАХ, а не повторениях
var plankTime = 0, plankTimer = null;

var recordBtn = document.getElementById('recordBtn');
var recordLabel = document.getElementById('recordLabel');
var hintsOverlay = document.getElementById('hintsOverlay');
var aiIndicator = document.getElementById('aiIndicator');

async function init() {
    try {
        document.getElementById('loadingText').textContent = 'Загрузка AI моделей...';
        
        const vision = await FilesetResolver.forVisionTasks(
            "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
        );
        
        faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
            baseOptions: { 
                modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task", 
                delegate: "GPU" 
            },
            runningMode: "VIDEO", 
            numFaces: 1
        });
        
        poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
            baseOptions: { 
                modelAssetPath: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task", 
                delegate: "GPU" 
            },
            runningMode: "VIDEO", 
            numPoses: 1
        });
        
        console.log('=== ВСЕ ЗАГРУЖЕНО ===');
        document.getElementById('loadingText').style.display = 'none';
        document.getElementById('startCamBtn').style.display = 'block';
        document.querySelector('.spinner').style.display = 'none';
    } catch (error) {
        console.error("Ошибка:", error);
        document.getElementById('loadingText').textContent = 'Ошибка: ' + error.message;
    }
}

function showInstructions() {
    const exName = document.getElementById('exerciseSelect').value;
    currentExercise = EXERCISES[exName];
    
    document.getElementById('instructionTitle').textContent = currentExercise.title;
    let html = '<div style="display: flex; flex-direction: column; gap: 20px;">';
    
    currentExercise.instructions.forEach((instruction, index) => {
        html += '<div style="display: flex; align-items: center; gap: 15px; padding: 15px; background: #f5f5f5; border-radius: 12px;">';
        html += '<div style="flex-shrink: 0; font-size: 24px; font-weight: bold; color: #667eea; min-width: 30px;">' + (index + 1) + '</div>';
        if (instruction.svg) {
            html += '<div style="flex-shrink: 0;">' + instruction.svg + '</div>';
        }
        html += '<div style="flex: 1; font-size: 16px;">' + (instruction.text || instruction) + '</div>';
        html += '</div>';
    });
    
    html += '</div>';
    
    if (currentExercise.name === 'plank') {
        html += '<p style="margin-top: 20px; font-weight: 600; text-align: center; color: #667eea;">Рекомендуемое время: ' + currentExercise.defaultReps + ' секунд</p>';
    } else {
        html += '<p style="margin-top: 20px; font-weight: 600; text-align: center; color: #667eea;">Рекомендуемое количество: ' + currentExercise.defaultReps + ' повторений</p>';
    }
    
    document.getElementById('instructionText').innerHTML = html;
    document.getElementById('instructionsScreen').style.display = 'flex';
}

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }
        });
        video.srcObject = stream;
        video.onloadedmetadata = () => {
            video.play().then(() => {
                running = true;
                document.getElementById('welcomeScreen').style.display = 'none';
                document.getElementById('overlayControls').style.display = 'block';
                recordBtn.disabled = false;
                recordLabel.textContent = 'Начать';
                aiIndicator.style.display = 'flex';
                detect();
            });
        };
    } catch (error) {
        alert("Камера недоступна: " + error.message);
    }
}

async function detect() {
    if (!running || video.readyState !== video.HAVE_ENOUGH_DATA) {
        requestAnimationFrame(detect);
        return;
    }
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    const isFace = currentExercise && currentExercise.name === 'neck';
    
    try {
        if (isFace) {
            const results = await faceLandmarker.detectForVideo(video, performance.now());
            if (results.faceLandmarks && results.faceLandmarks.length > 0) {
                const draw = new DrawingUtils(ctx);
                const lm = results.faceLandmarks[0];
                draw.drawConnectors(lm, FaceLandmarker.FACE_LANDMARKS_TESSELATION, {color: '#00FF00', lineWidth: 2});
                draw.drawConnectors(lm, FaceLandmarker.FACE_LANDMARKS_LEFT_EYE, {color: '#FF0000', lineWidth: 3});
                draw.drawConnectors(lm, FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE, {color: '#FF0000', lineWidth: 3});
                if (recording && currentExercise) analyzeExercise(lm);
            }
        } else {
            const results = await poseLandmarker.detectForVideo(video, performance.now());
            if (results.landmarks && results.landmarks.length > 0) {
                const draw = new DrawingUtils(ctx);
                const lm = results.landmarks[0];
                draw.drawConnectors(lm, PoseLandmarker.POSE_CONNECTIONS, {color: '#00FF00', lineWidth: 5});
                draw.drawLandmarks(lm, {color: '#FF0000', radius: 8, fillColor: '#FFFF00'});
                if (recording && currentExercise) analyzeExercise(lm);
            }
        }
    } catch (error) {
        console.error("Ошибка детекции:", error);
    }
    
    requestAnimationFrame(detect);
}

// ВОТ ЗДЕСЬ ПЕРЕДАЕМ plankTime ДЛЯ ПЛАНКИ
// Потому что планка измеряется временем, а не повторениями
function analyzeExercise(lm) {
    let result;
    
    // Для планки передаем дополнительный параметр plankTime
    if (currentExercise.name === 'plank') {
        result = currentExercise.analyze(lm, exerciseState, showHint, logError, calcAngle, plankTime);
    } else {
        result = currentExercise.analyze(lm, exerciseState, showHint, logError, calcAngle);
    }
    
    if (result.counted) {
        counter++;
        if (result.correct) {
            correct++;
        } else {
            incorrect++;
        }
        updateUI();
    }
    
    updateStatus(result.status);
}

function showHint(msg, icon, bgColor = 'rgba(239, 68, 68, 0.95)', duration = 2500) {
    if (!hintsEnabled) return;
    hintsOverlay.innerHTML = '';
    
    const hint = document.createElement('div');
    hint.className = 'hint-indicator';
    hint.innerHTML = `<div style="display: flex; align-items: center; gap: 16px;">
        <div style="flex-shrink: 0; animation: bounce 0.5s infinite;">${icon}</div>
        <div style="font-size: 20px; font-weight: 700; line-height: 1.4;">${msg}</div>
    </div>`;
    
    hint.style.background = bgColor;
    hint.style.left = '50%';
    hint.style.top = '50%';
    hint.style.transform = 'translate(-50%, -50%)';
    
    hintsOverlay.appendChild(hint);
    setTimeout(() => { if (hintsOverlay.contains(hint)) hintsOverlay.removeChild(hint); }, duration);
}


function logError(msg) {
    errorLog.push({ repNumber: counter + 1, message: msg });
}

function calcAngle(a, b, c) {
    const rad = Math.atan2(c.y - b.y, c.x - b.x) - Math.atan2(a.y - b.y, a.x - b.x);
    let angle = Math.abs(rad * 180 / Math.PI);
    return angle > 180 ? 360 - angle : angle;
}

function updateUI() {
    document.getElementById('reps').textContent = counter;
    document.getElementById('correct').textContent = correct;
    document.getElementById('incorrect').textContent = incorrect;
}

function updateStatus(text) {
    document.getElementById('status').textContent = text;
}

function toggleRecording() {
    if (!recording) showInstructions();
    else stopExercise();
}

function startExercise() {
    document.getElementById('instructionsScreen').style.display = 'none';
    counter = 0; 
    correct = 0; 
    incorrect = 0; 
    errorLog = [];
    exerciseState = currentExercise.getInitialState();
    plankTime = 0;
    updateUI();
    
    const cd = document.getElementById('countdown');
    let count = 3;
    cd.style.display = 'block';
    cd.textContent = count;
    recordBtn.disabled = true;
    
    const timer = setInterval(() => {
        count--;
        if (count > 0) {
            cd.textContent = count;
        } else {
            cd.textContent = 'СТАРТ!';
            setTimeout(() => {
                cd.style.display = 'none';
                recording = true;
                recordBtn.disabled = false;
                recordBtn.classList.add('recording');
                recordLabel.textContent = 'Стоп';
                
                // ВАЖНО: Таймер запускается ТОЛЬКО для планки
                // Потому что планка - это единственное упражнение на время
                if (currentExercise.name === 'plank') {
                    plankTimer = setInterval(() => { 
                        plankTime += 0.1; 
                    }, 100);
                }
            }, 500);
            clearInterval(timer);
        }
    }, 1000);
}

function stopExercise() {
    recording = false;
    recordBtn.classList.remove('recording');
    recordLabel.textContent = 'Начать';
    hintsOverlay.innerHTML = '';
    
    // Останавливаем таймер планки если он был запущен
    if (plankTimer) {
        clearInterval(plankTimer);
        plankTimer = null;
    }
    
    const total = correct + incorrect;
    const score = total > 0 ? Math.round((correct / total) * 100) : (correct > 0 ? 100 : 0);
    
    fetch('/api/save-pe-result', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            exercise_type: currentExercise.name,
            repetitions: counter,
            correct_count: correct,
            incorrect_count: incorrect,
            errors: errorLog.map(e => e.message),
            score: score,
            // Для планки сохраняем время
            time: currentExercise.name === 'plank' ? plankTime : null
        })
    }).then(() => showResults(score));
}

function showResults(score) {
    let html = '<p><strong>Упражнение:</strong> ' + currentExercise.title + '</p>';
    
    // Для планки показываем время вместо повторений
    if (currentExercise.name === 'plank') {
        html += '<p><strong>Время удержания:</strong> ' + plankTime.toFixed(1) + ' из ' + currentExercise.defaultReps + ' секунд</p>';
    } else {
        html += '<p><strong>Повторений:</strong> ' + counter + ' из ' + currentExercise.defaultReps + '</p>';
    }
    
    html += '<p><strong>Правильных:</strong> ' + correct + '</p>';
    html += '<p><strong>С ошибками:</strong> ' + incorrect + '</p>';
    html += '<p><strong>Оценка:</strong> ' + score + '%</p>';
    
    document.getElementById('resultsText').innerHTML = html;
    
    if (errorLog.length > 0) {
        let err = '<h3>Детальный отчет по ошибкам</h3>';
        errorLog.forEach((e) => {
            err += '<div class="error-item"><strong>Повторение №' + e.repNumber + ':</strong> ' + e.message + '</div>';
        });
        document.getElementById('errorReport').innerHTML = err;
    } else {
        document.getElementById('errorReport').innerHTML = '<p style="color: #10b981; font-weight: 600;">✅ Все повторения выполнены идеально!</p>';
    }
    document.getElementById('resultsOverlay').style.display = 'flex';
}

window.restartExercise = () => {
    document.getElementById('resultsOverlay').style.display = 'none';
};

document.getElementById('startCamBtn').onclick = startCamera;
document.getElementById('recordBtn').onclick = toggleRecording;
document.getElementById('startExerciseBtn').onclick = startExercise;
document.getElementById('closeBtn').onclick = () => { location.href = '/'; };
document.getElementById('hintsToggle').onchange = (e) => { hintsEnabled = e.target.checked; };

init();
