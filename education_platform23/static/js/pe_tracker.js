import {PoseLandmarker, FilesetResolver, DrawingUtils} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0";

let poseLandmarker;
let webcamRunning = false;
let videoElement;
let canvasElement;
let canvasCtx;
let currentExercise = 'squat';
let exerciseCounter = 0;
let correctCount = 0;
let incorrectCount = 0;
let errors = [];
let isRecording = false;
let countdownTimer = null;

// Инициализация MediaPipe
async function initializePoseLandmarker() {
    const vision = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm"
    );
    
    poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
        baseOptions: {
            modelAssetPath: `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task`,
            delegate: "GPU"
        },
        runningMode: "VIDEO",
        numPoses: 1
    });
}

// Запуск камеры
async function enableCam() {
    if (!poseLandmarker) {
        alert("Модель еще загружается. Подождите...");
        return;
    }

    videoElement = document.getElementById("webcam");
    canvasElement = document.getElementById("output_canvas");
    canvasCtx = canvasElement.getContext("2d");

    const constraints = { video: true };

    navigator.mediaDevices.getUserMedia(constraints).then((stream) => {
        videoElement.srcObject = stream;
        videoElement.addEventListener("loadeddata", predictWebcam);
        webcamRunning = true;
    });
}

// Обнаружение позы
async function predictWebcam() {
    if (!webcamRunning) return;

    canvasElement.width = videoElement.videoWidth;
    canvasElement.height = videoElement.videoHeight;

    let startTimeMs = performance.now();
    const results = await poseLandmarker.detectForVideo(videoElement, startTimeMs);

    canvasCtx.save();
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);

    if (results.landmarks && results.landmarks.length > 0) {
        const drawingUtils = new DrawingUtils(canvasCtx);
        
        for (const landmark of results.landmarks) {
            drawingUtils.drawLandmarks(landmark, {
                radius: 4,
                color: '#FF0000',
                fillColor: '#00FF00'
            });
            drawingUtils.drawConnectors(landmark, PoseLandmarker.POSE_CONNECTIONS, {
                color: '#00FF00',
                lineWidth: 2
            });

            // Анализ упражнения если идет запись
            if (isRecording) {
                analyzeExercise(landmark);
            }
        }
    }

    canvasCtx.restore();
    window.requestAnimationFrame(predictWebcam);
}

// Анализ упражнения
function analyzeExercise(landmarks) {
    if (currentExercise === 'squat') {
        analyzeSquat(landmarks);
    } else if (currentExercise === 'pushup') {
        analyzePushup(landmarks);
    } else if (currentExercise === 'plank') {
        analyzePlank(landmarks);
    }
}

// Анализ приседаний
function analyzeSquat(landmarks) {
    const leftHip = landmarks[23];
    const leftKnee = landmarks[25];
    const leftAnkle = landmarks[27];
    const rightHip = landmarks[24];
    const rightKnee = landmarks[26];
    const rightAnkle = landmarks[28];

    // Вычисляем угол в колене
    const leftKneeAngle = calculateAngle(leftHip, leftKnee, leftAnkle);
    const rightKneeAngle = calculateAngle(rightHip, rightKnee, rightAnkle);

    const avgKneeAngle = (leftKneeAngle + rightKneeAngle) / 2;

    // Проверка правильности приседания
    if (avgKneeAngle < 100) {
        // Глубокое приседание
        exerciseCounter++;
        
        // Проверка ошибок
        const hipWidth = Math.abs(leftHip.x - rightHip.x);
        const kneeWidth = Math.abs(leftKnee.x - rightKnee.x);
        
        if (kneeWidth > hipWidth * 1.2) {
            errors.push(`Приседание ${exerciseCounter}: колени слишком широко расставлены`);
            incorrectCount++;
        } else if (leftHip.y < leftKnee.y || rightHip.y < rightKnee.y) {
            errors.push(`Приседание ${exerciseCounter}: недостаточная глубина`);
            incorrectCount++;
        } else {
            correctCount++;
        }
        
        updateUI();
    }
}

// Анализ отжиманий
function analyzePushup(landmarks) {
    const leftShoulder = landmarks[11];
    const leftElbow = landmarks[13];
    const leftWrist = landmarks[15];
    const rightShoulder = landmarks[12];
    const rightElbow = landmarks[14];
    const rightWrist = landmarks[16];

    const leftElbowAngle = calculateAngle(leftShoulder, leftElbow, leftWrist);
    const rightElbowAngle = calculateAngle(rightShoulder, rightElbow, rightWrist);
    const avgElbowAngle = (leftElbowAngle + rightElbowAngle) / 2;

    if (avgElbowAngle < 90) {
        exerciseCounter++;
        
        // Проверка прямой спины
        const leftHip = landmarks[23];
        const rightHip = landmarks[24];
        const backAngle = Math.abs(leftShoulder.y - leftHip.y);
        
        if (backAngle < 0.3) {
            errors.push(`Отжимание ${exerciseCounter}: прогиб в пояснице`);
            incorrectCount++;
        } else {
            correctCount++;
        }
        
        updateUI();
    }
}

// Анализ планки
function analyzePlank(landmarks) {
    const leftShoulder = landmarks[11];
    const leftHip = landmarks[23];
    const leftAnkle = landmarks[27];
    
    // Проверка прямой линии тела
    const bodyAngle = calculateAngle(leftShoulder, leftHip, leftAnkle);
    
    if (bodyAngle < 170 || bodyAngle > 190) {
        errors.push('Планка: тело не образует прямую линию');
        incorrectCount++;
    } else {
        correctCount++;
    }
    
    updateUI();
}

// Вычисление угла между тремя точками
function calculateAngle(point1, point2, point3) {
    const radians = Math.atan2(point3.y - point2.y, point3.x - point2.x) -
                   Math.atan2(point1.y - point2.y, point1.x - point2.x);
    let angle = Math.abs(radians * 180.0 / Math.PI);
    
    if (angle > 180.0) {
        angle = 360 - angle;
    }
    
    return angle;
}

// Обновление UI
function updateUI() {
    document.getElementById('counter').textContent = exerciseCounter;
    document.getElementById('correct').textContent = correctCount;
    document.getElementById('incorrect').textContent = incorrectCount;
}

// Старт упражнения с обратным отсчетом
function startExercise() {
    const exercise = document.getElementById('exercise-select').value;
    currentExercise = exercise;
    
    // Сброс счетчиков
    exerciseCounter = 0;
    correctCount = 0;
    incorrectCount = 0;
    errors = [];
    updateUI();
    
    // Обратный отсчет 3-2-1
    let countdown = 3;
    const countdownEl = document.getElementById('countdown');
    countdownEl.style.display = 'block';
    countdownEl.textContent = countdown;
    
    countdownTimer = setInterval(() => {
        countdown--;
        if (countdown > 0) {
            countdownEl.textContent = countdown;
        } else {
            countdownEl.textContent = 'СТАРТ!';
            setTimeout(() => {
                countdownEl.style.display = 'none';
                isRecording = true;
            }, 500);
            clearInterval(countdownTimer);
        }
    }, 1000);
}

// Остановка упражнения
function stopExercise() {
    isRecording = false;
    
    // Вычисляем оценку
    const total = correctCount + incorrectCount;
    const score = total > 0 ? Math.round((correctCount / total) * 100) : 0;
    
    // Отправляем результаты на сервер
    fetch('/api/save-pe-result', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            exercise_type: currentExercise,
            repetitions: exerciseCounter,
            correct_count: correctCount,
            incorrect_count: incorrectCount,
            errors: errors,
            score: score
        })
    }).then(response => response.json())
      .then(data => {
          showResults(score);
      });
}

// Показать результаты
function showResults(score) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = `
        <h3>Результаты тренировки</h3>
        <p>Упражнение: ${getExerciseName(currentExercise)}</p>
        <p>Всего повторений: ${exerciseCounter}</p>
        <p>Правильных: ${correctCount}</p>
        <p>С ошибками: ${incorrectCount}</p>
        <p>Оценка: ${score}%</p>
        <h4>Ошибки:</h4>
        <ul>
            ${errors.length > 0 ? errors.map(e => `<li>${e}</li>`).join('') : '<li>Ошибок не обнаружено!</li>'}
        </ul>
    `;
    resultsDiv.style.display = 'block';
}

function getExerciseName(type) {
    const names = {
        'squat': 'Приседания',
        'pushup': 'Отжимания',
        'plank': 'Планка'
    };
    return names[type] || type;
}

// Глобальные функции для кнопок
window.enableCam = enableCam;
window.startExercise = startExercise;
window.stopExercise = stopExercise;

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    initializePoseLandmarker();
});
