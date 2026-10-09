<!-- Text extract of Product_Specification_ReflexEnglish_v1.1.docx so agents and diffs can read it. The .docx remains the source of truth. -->

Product Specification: ReflexEnglish
Visual-First English Reflex Platform dành cho học sinh (v1.1 MVP)
| Thông số dự án | Chi tiết |
|---|---|
| Tên dự án | ReflexEnglish |
| Phiên bản | v1.1 (MVP) – thay thế v1.0 ngày 08/10/2026 |
| Ngày cập nhật | 09/10/2026 |
| Đối tượng | Học sinh phổ thông (giả định 11–18 tuổi, THCS–THPT), trình độ CEFR A1–B1 |
| Nền tảng | Mobile-first Web App (PWA ready) |
| Mục tiêu cốt lõi | Rút ngắn độ trễ dịch thầm: nhìn vật thể → nói tiếng Anh trong vài giây, không qua tiếng Việt |
| Nguyên tắc kinh tế | Gọi AI (Gemini) đúng 1 lần cho mỗi ảnh duy nhất, lưu kết quả vào DB, mọi người dùng sau đó đọc từ DB. |

# 0. Thay đổi so với v1.0
| Hạng mục | Thay đổi |
|---|---|
| Persona | Xác định rõ là học sinh; bổ sung ràng buộc an toàn, riêng tư và sư phạm (mục 2). |
| Pipeline AI | Gọi Gemini 1 lần/ảnh, lưu DB, dùng chung cho mọi người; chống trùng ảnh bằng hash (mục 4). |
| Reflex Mode | Tính năng mới, cốt lõi của sản phẩm: ẩn nhãn, đếm ngược, đo thời gian phản hồi (mục 3.3). |
| Chấm điểm | Tách 3 điểm: Accuracy, Pronunciation, Reflex. Bỏ cam kết "chỉnh khẩu hình/trọng âm" bằng Whisper (mục 3.2). |
| Schema DB | Sửa lỗi SQL; tách nội dung dùng chung (card_contents) khỏi thẻ của người dùng (cards); thêm card_labels, audio_assets, attempts, review_state; RLS (mục 5). |
| Prompt | Structured output: bounding box, bản dịch tiếng Việt, CEFR, đáp án chấp nhận, cờ an toàn (mục 6). |
| Chia sẻ UGC | Mặc định private; chia sẻ phải qua kiểm duyệt; có bước người dùng xem lại kết quả AI (mục 2, 3.1). |
| Lộ trình | Từ 4 tuần thành Tuần 0 (spike) + 6 tuần, có pilot với 1 lớp (mục 9). |

# 1. Tổng quan & Mục tiêu sản phẩm

## 1.1. Vấn đề
- Độ trễ dịch thầm: học sinh biết từ và ngữ pháp nhưng nói chậm vì nghĩ tiếng Việt trước rồi dịch sang tiếng Anh.
- Học từ rời rạc: danh sách từ không gắn với hình ảnh đời sống nên khó nhớ và khó gọi ra nhanh.
- Ít cơ hội nói: trong lớp đông, mỗi học sinh nói rất ít; học sinh ngại nói trước người khác.

## 1.2. Giải pháp
Học sinh nhìn ảnh đời thường (ảnh hệ thống cung cấp hoặc ảnh tự chụp) và luyện nói theo 3 tầng nhận thức, sau đó được thử thách bằng Reflex Mode:
- Level 1 – Labeling: gọi tên từng vật thể ngay khi nhìn thấy.
- Level 2 – Describing: 1–2 câu đơn mô tả hành động, trạng thái.
- Level 3 – Storytelling: kể lại 2–3 câu có ngữ cảnh.
- Reflex Mode: ẩn chữ, chỉ cho nhìn vật thể và đếm ngược; học sinh phải nói tiếng Anh trước khi hết giờ. Hệ thống đo thời gian bắt đầu nói.

## 1.3. Chỉ số thành công (MVP, đo trong pilot)
| Chỉ số | Mục tiêu pilot | Cách đo |
|---|---|---|
| Thời gian phản hồi trung vị (Level 1, Reflex) | Giảm ≥ 25% sau 3 tuần | attempts.reflex_ms theo tuần |
| Học sinh quay lại D7 | ≥ 35% | Đăng nhập + ít nhất 1 phiên luyện |
| Số phiên luyện/học sinh/tuần | ≥ 3 phiên (mỗi phiên ~5 phút) | attempts nhóm theo phiên |
| Tỉ lệ nhãn AI sai bị học sinh/giáo viên sửa | < 10% | Số lần sửa/số nhãn hiển thị |
| Chi phí AI trên mỗi học sinh hoạt động | Theo dõi, ngưỡng đặt sau spike Tuần 0 | Số lần gọi Gemini / người dùng |

# 2. Persona & Ràng buộc dành cho học sinh

## 2.1. Persona
| Thuộc tính | Mô tả |
|---|---|
| Học sinh | Lớp 6–12, dùng điện thoại của gia đình hoặc cá nhân; học tiếng Anh trên lớp theo chương trình GDPT 2018 (đích A2 cuối THCS, B1 cuối THPT – cần xác nhận với giáo viên pilot). |
| Nhu cầu | Tự tin nói nhanh; luyện ngắn (3–5 phút) sau giờ học; không bị chấm điểm công khai. |
| Nỗi đau | Ngại nói sai, nghĩ lâu rồi mới nói, từ vựng sách giáo khoa khó gắn với đời sống. |
| Người liên quan | Phụ huynh (đồng ý sử dụng, có thể xem tiến độ); giáo viên (giao chủ đề, xem lớp) – giáo viên là vai trò mở rộng sau MVP, nhưng schema có sẵn role. |

## 2.2. Ràng buộc bắt buộc
- Dữ liệu cá nhân của trẻ: theo Nghị định 13/2023/NĐ-CP, trẻ dưới 16 tuổi cần có sự đồng ý của cha mẹ/người giám hộ. Lưu birth_year và guardian_consent_at; chặn đăng ký nếu thiếu. Cần xác nhận với bộ phận pháp lý trước khi pilot.
- Hồ sơ tối thiểu: biệt danh và avatar chọn sẵn; không thu họ tên thật, số điện thoại, vị trí. Không hiển thị địa điểm chụp.
- Ảnh: xóa toàn bộ EXIF (đặc biệt GPS) ngay khi upload; chỉ lưu bản đã xử lý.
- Mặc định private. Ảnh chỉ hiển thị cho chủ sở hữu. Chia sẻ (public hoặc theo lớp) chỉ khi đạt kiểm duyệt (mục 3.1).
- Không có bảng xếp hạng công khai giữa học sinh. Động lực dùng streak cá nhân, XP và huy hiệu; so sánh với chính mình.
- Phản hồi tích cực: không chấm "sai" gay gắt; luôn đưa bước sửa tiếp theo.
- Phiên học ngắn: một phiên mặc định 10 mục (~3–5 phút); nhắc nghỉ nếu dùng quá 20 phút/ngày (cấu hình được).
- Từ vựng và chủ đề phù hợp lứa tuổi: cờ is_suitable_for_students do Gemini trả về cùng lần gọi (mục 6).

# 3. Luồng nghiệp vụ & Tính năng cốt lõi

## 3.1. Module 1 – AI Vision Pipeline ("Gọi AI một lần – dùng nhiều lần")
Mục tiêu: mỗi ảnh duy nhất chỉ tốn đúng một lần gọi Gemini. Mọi lần đọc, luyện tập hay chia sẻ sau đó không gọi AI.
- Upload/chụp: client nén ảnh (cạnh dài tối đa ~1280px), gửi lên backend.
- Làm sạch: backend xóa EXIF, tính sha256 và perceptual hash (phash).
- Tra cứu trùng: nếu sha256 đã có trong image_assets và card_contents.status = ready thì dùng lại nội dung, chỉ tạo một dòng cards mới cho người dùng; không gọi Gemini. Nếu phash gần giống (khoảng cách Hamming nhỏ) thì gợi ý "ảnh tương tự đã có" để người dùng chọn dùng lại.
- Chưa có: tạo card_contents(status = processing) trong transaction (khóa theo sha256, tránh hai người upload cùng lúc gọi AI hai lần), đưa job vào hàng đợi.
- Một lần gọi Gemini với structured output, trả về toàn bộ: topic, tags, CEFR, labels (bounding box, IPA, nghĩa tiếng Việt, accepted_answers), descriptions (en + vi), story (en + vi), cờ an toàn.
- Kiểm tra: validate bằng pydantic; nếu JSON sai thì thử lại tối đa 2 lần (đây là thử lại cùng một ảnh vì lỗi, ghi lại số lần gọi thực tế).
- Âm thanh một lần: sinh TTS bằng giọng nam trẻ neural tự nhiên của Microsoft (không dùng giọng máy của trình duyệt) cho từng từ/câu, lưu audio_assets (khóa text + voice, dùng chung giữa mọi ảnh). Từ "coffee cup" xuất hiện ở nhiều ảnh chỉ sinh một lần.
- Ghi DB: card_contents + card_labels, status = ready. Các lần mở bài sau chỉ đọc DB và Storage.
- Xem lại & chỉnh: trước khi lưu thẻ, học sinh thấy kết quả AI và có thể kéo marker, xóa hoặc đổi nhãn sai. Sửa đổi lưu thành revision thuộc thẻ của người đó, không ghi đè nội dung dùng chung.
- Chia sẻ: private → "Chia sẻ" → nếu cờ an toàn sạch (không mặt người rõ, không thông tin cá nhân, không nhạy cảm) thì tự động duyệt; ngược lại vào hàng chờ kiểm duyệt. Từ chối thì giữ private.

## 3.2. Module 2 – Màn hình luyện tập (Practice Screen)
- Visual marker: chấm tròn trên ảnh theo tọa độ tâm của bounding box. Ảnh phải render bằng object-contain (hoặc quy đổi tọa độ theo vùng hiển thị) để marker không lệch khi ảnh bị cắt. Vùng chạm tối thiểu 44px.
- Tab Level 1/2/3: Level 1 hiển thị IPA; bản dịch tiếng Việt ẩn mặc định, chỉ hiện khi bấm "Xem nghĩa" (giữ nguyên tắc Think in English).
- Mở khóa tuần tự: Level 2 mở khi đạt ≥ 70% Level 1; Level 3 mở khi đạt ≥ 70% Level 2.
- Shadowing: giữ nút để ghi âm (Pointer Events, xử lý pointercancel); nghe lại bản thu và bản mẫu.
- Chấm điểm – tách 3 chỉ số:
- Accuracy: transcript khớp từ/câu mong đợi (hoặc accepted_answers).
- Pronunciation: MVP dùng độ tin cậy STT; nếu spike Tuần 0 đạt yêu cầu thì dùng API chấm phát âm theo âm vị. Không hứa chỉnh khẩu hình/trọng âm nếu chưa có nguồn dữ liệu âm vị.
- Reflex: thời gian phản hồi (mục 3.3), chỉ áp dụng ở Reflex Mode.
- Tự động nghe & nói theo: nút một chạm; hệ thống đọc mẫu → bíp → mở micro vài giây → nhận xét → câu kế tiếp, lần lượt hết danh sách của cấp độ hiện tại. Dừng được bất kỳ lúc nào.
- Trạng thái lỗi: từ chối quyền mic, không nghe thấy tiếng, quá ồn, mạng chậm – mỗi trường hợp có thông báo và nút thử lại.

## 3.3. Reflex Mode (tính năng mới)
Mục tiêu: huấn luyện nối thẳng "hình ảnh → từ/câu tiếng Anh" trong vài giây, bỏ bước dịch.
| Thành phần | Quy tắc |
|---|---|
| Một vòng (round) | Ảnh hiện, một marker sáng lên (và ẩn nhãn). Đồng hồ đếm ngược bắt đầu. Học sinh nói từ/câu tương ứng. Hết giờ hoặc nói xong thì hiện đáp án + audio mẫu. |
| Một phiên | 10 vòng lấy từ review_state đến hạn (ưu tiên từ yếu), trộn từ mới. Kết thúc có màn tổng kết. |
| Cấp độ | R1: Nhìn–nói có gợi ý (chữ cái đầu, 6 giây). R2: Không gợi ý (5 giây). R3: Không gợi ý (3 giây). R4: Câu mô tả cho vùng được tô sáng (8 giây). |
| Đo thời gian | reflex_ms = thời điểm phát hiện bắt đầu nói (VAD trên Web Audio) trừ thời điểm marker xuất hiện. Không dùng thời điểm STT trả về cuối vì bị trễ. |
| Điểm Reflex | Accuracy (60%) + Speed (40%). Speed = 100 nếu ≤ 1.0s; giảm tuyến tính về 0 tại giới hạn của cấp độ. |
| Phản hồi | Nhanh & đúng: "Phản xạ tốt". Đúng nhưng chậm: gợi ý luyện lại. Sai: hiện đáp án, đánh dấu vào hàng đợi ôn. |
| Từ đồng nghĩa | Chấp nhận accepted_answers (ví dụ cup/mug) để học sinh không bị phạt oan. |
| Tiến trình | Đạt ≥ 80% ở một cấp độ trong 2 phiên liên tiếp thì mở cấp độ kế tiếp. Điểm và thời gian cập nhật review_state. |
| Chế độ tự động (rảnh tay) | Một lần chạm để bắt đầu, sau đó không cần chạm: đếm ngược, bíp báo đến lượt, tự mở micro, tự chấm, tự đọc đáp án rồi tự sang vòng kế. Có nút Dừng. Cần micro; không có micro thì chạy ở chế độ nghe và nói theo, không chấm điểm (không tính vào độ nhớ). |
| An toàn trải nghiệm | Không hiển thị thời gian "thua" gay gắt; có nút Bỏ qua; có chế độ không đếm giờ cho học sinh lo lắng (vẫn đo thời gian nhưng ẩn đồng hồ). |

## 3.4. Module 3 – Thư viện cá nhân & Ôn tập
- Tab: Bài của tôi, Đã lưu, Cần ôn lại (thẻ có từ đến hạn trong review_state).
- Tìm kiếm theo từ vựng: truy vấn card_labels.word (chỉ mục lower(word)); lọc theo chủ đề topic và tag.
- Spaced repetition: MVP dùng SM-2 đơn giản theo từng từ/câu (review_state), không theo cả thẻ. Chuyển sang FSRS khi có đủ dữ liệu.
- Độ nhớ của thẻ: trung bình điểm kết hợp (Accuracy 60% + Speed 40%) của các từ trong thẻ ở 5 lần thử gần nhất; chia ngưỡng <60% Cần ôn, 60–84% Đang học, ≥85% Đã thuộc.

## 3.5. Module 4 – Khám phá (đọc, MVP tối thiểu)
- Hiển thị thẻ hệ thống tạo sẵn (seed) và thẻ cộng đồng đã duyệt, lọc theo chủ đề và cấp độ.
- Hành động: Lưu thẻ, Luyện, Báo cáo. Người dùng luyện trên nội dung đã có trong DB, không phát sinh gọi AI.
- Chưa làm trong MVP: bình luận, theo dõi, bảng xếp hạng.

# 4. Kiến trúc kỹ thuật
| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Frontend | Next.js (App Router), Tailwind CSS (cài làm package, ghim phiên bản) | Mobile-first PWA, MediaRecorder/Web Audio để thu âm và đo VAD; Pointer Events cho nút giữ để nói. |
| Backend | FastAPI (Python 3.11+) | API, job nền (hàng đợi), validate JSON, gọi Gemini, sinh TTS. |
| AI | Gemini Flash (phiên bản vision ổn định mới nhất lúc triển khai), structured output | Một lần gọi cho mỗi ảnh duy nhất: nhận diện, nội dung 3 tầng, dịch, an toàn. |
| TTS | Azure AI Speech, giọng nam trẻ neural en-US-BrianNeural, cao độ +20Hz, tốc độ -8% | Sinh một lần, cache theo (text, voice) trong audio_assets. Microsoft không có giọng bé trai tiếng Anh nên dùng giọng nam trẻ nâng cao độ (lựa chọn khác: en-US-AnaNeural, giọng trẻ em nữ). Prototype dùng edge-tts (không chính thức) với cùng giọng; bản thật dùng Azure chính thức. Không có file thì trình duyệt đọc dự phòng, ưu tiên giọng nam. |
| STT/chấm điểm | Web Speech API trên thiết bị (nếu hỗ trợ) + STT server dự phòng | Chạy mỗi lượt luyện, không thể cache; ưu tiên chạy trên thiết bị để giảm chi phí và độ trễ. Chốt sau spike Tuần 0. |
| DB & Storage | Supabase (PostgreSQL + Auth + Storage + RLS) | Dữ liệu có cấu trúc, ảnh đã xóa EXIF, file audio. |

## 4.1. Luồng "AI một lần" và đường đọc
UPLOAD  -> strip EXIF -> sha256/phash -> image_assets
|-- sha256 da co & content.ready  -> TAO cards moi, KHONG goi AI
|-- chua co -> card_contents(processing) -> job
1 lan Gemini (structured output) -> validate
-> TTS (cache theo text+voice) -> card_labels
-> card_contents(ready)
DOC / LUYEN TAP / CHIA SE : chi doc DB + Storage, 0 lan goi AI
MOI LUOT NOI : STT (tren thiet bi hoac server) - khong the cache
- Chi phí AI tỉ lệ với số ảnh duy nhất, không phụ thuộc số người học. Ảnh hệ thống (seed) được xử lý trước hàng loạt.
- Khóa chống gọi trùng: unique(sha256) + trạng thái processing; người upload thứ hai chờ kết quả đang chạy.
- Phiên bản prompt: lưu prompt_version và model; nâng cấp prompt thì chỉ chạy lại cho nội dung được chọn (có kiểm soát chi phí), không tự động chạy lại toàn bộ.
- Thử lại khi lỗi: tối đa 2 lần/ảnh; sau đó status = failed và người dùng được thông báo.

# 5. Cấu trúc cơ sở dữ liệu (v1.1)
Nội dung do AI sinh ra (card_contents, card_labels) tách khỏi thẻ của người dùng (cards). Nhiều thẻ có thể trỏ tới cùng một nội dung, nên dữ liệu AI chỉ tạo và lưu một lần.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- 1. Hồ sơ (liên kết Supabase Auth)
CREATE TABLE profiles (
id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
username VARCHAR(30) UNIQUE NOT NULL,
display_name VARCHAR(60) NOT NULL,          -- biệt danh, không dùng tên thật
avatar_key TEXT,                            -- chọn từ bộ avatar có sẵn
birth_year SMALLINT,
guardian_consent_at TIMESTAMPTZ,            -- bắt buộc nếu dưới 16 tuổi
cefr_level TEXT NOT NULL DEFAULT 'A1',
role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student','teacher','admin')),
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- 2. Ảnh đã xử lý (dedupe theo hash)
CREATE TABLE image_assets (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
sha256 CHAR(64) UNIQUE NOT NULL,
phash BIGINT,
storage_path TEXT NOT NULL,                 -- bản đã xóa EXIF
width INT, height INT,
first_uploaded_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- 3. Nội dung AI dùng chung: kết quả của đúng 1 lần gọi Gemini cho 1 ảnh
CREATE TABLE card_contents (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
image_asset_id UUID UNIQUE NOT NULL REFERENCES image_assets(id) ON DELETE CASCADE,
status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing','ready','failed')),
model TEXT, prompt_version TEXT, ai_calls SMALLINT NOT NULL DEFAULT 0,
topic TEXT, topic_tags TEXT[] NOT NULL DEFAULT '{}', cefr_level TEXT,
descriptions JSONB,                         -- [{en, vi, audio_id}]
story_en TEXT, story_vi TEXT, story_audio_id UUID,
safety JSONB,                               -- cờ an toàn từ Gemini
moderation_status TEXT NOT NULL DEFAULT 'pending'
CHECK (moderation_status IN ('pending','approved','rejected')),
raw_response JSONB,                         -- để audit/chạy lại parser
error TEXT,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- 4. Nhãn vật thể (phục vụ tìm kiếm theo từ vựng và marker)
CREATE TABLE card_labels (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
content_id UUID NOT NULL REFERENCES card_contents(id) ON DELETE CASCADE,
position SMALLINT NOT NULL,
word TEXT NOT NULL, ipa TEXT, vi_meaning TEXT,
accepted_answers TEXT[] NOT NULL DEFAULT '{}',
cefr_level TEXT, confidence REAL,
x REAL NOT NULL CHECK (x BETWEEN 0 AND 1),   -- tâm bounding box (đã chuẩn hóa)
y REAL NOT NULL CHECK (y BETWEEN 0 AND 1),
box_x1 REAL, box_y1 REAL, box_x2 REAL, box_y2 REAL,
audio_id UUID
);
CREATE INDEX card_labels_word_idx ON card_labels (lower(word));
-- 5. Âm thanh dùng chung (sinh một lần theo text + voice)
CREATE TABLE audio_assets (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
text TEXT NOT NULL, voice TEXT NOT NULL,
storage_path TEXT NOT NULL, duration_ms INT,
UNIQUE (text, voice)
);
-- 6. Thẻ của người dùng (tham chiếu nội dung dùng chung)
CREATE TABLE cards (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
content_id UUID NOT NULL REFERENCES card_contents(id) ON DELETE RESTRICT,
title VARCHAR(80),
visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','class','public')),
published_at TIMESTAMPTZ,
view_count INT NOT NULL DEFAULT 0,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
UNIQUE (owner_id, content_id)
);
-- 7. Lưu thẻ từ cộng đồng
CREATE TABLE card_saves (
user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
PRIMARY KEY (user_id, card_id)
);
-- 8. Mỗi lượt luyện (shadowing hoặc reflex)
CREATE TABLE attempts (
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
item_type TEXT NOT NULL CHECK (item_type IN ('label','sentence','story')),
item_id UUID NOT NULL,
mode TEXT NOT NULL CHECK (mode IN ('shadow','reflex')),
reflex_level SMALLINT,                       -- R1..R4
transcript TEXT,
accuracy SMALLINT, pronunciation SMALLINT, reflex_ms INT, reflex_score SMALLINT,
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX attempts_user_time_idx ON attempts (user_id, created_at DESC);
-- 9. Lịch ôn tập (SM-2) theo từng từ/câu
CREATE TABLE review_state (
user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
item_type TEXT NOT NULL, item_id UUID NOT NULL,
ease REAL NOT NULL DEFAULT 2.5, interval_days INT NOT NULL DEFAULT 0,
reps INT NOT NULL DEFAULT 0, lapses INT NOT NULL DEFAULT 0,
due_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), last_reviewed_at TIMESTAMPTZ,
PRIMARY KEY (user_id, item_type, item_id)
);
CREATE INDEX review_due_idx ON review_state (user_id, due_at);

## 5.1. Chính sách RLS (bắt buộc bật)
- cards: chủ sở hữu đọc/ghi thẻ của mình; người khác chỉ đọc khi visibility ≠ private và card_contents.moderation_status = approved.
- card_contents, card_labels, audio_assets: chỉ đọc qua thẻ mà người dùng có quyền xem; ghi chỉ bằng service role của backend (client không ghi trực tiếp).
- attempts, review_state, card_saves: chỉ người sở hữu đọc/ghi.
- profiles: người dùng chỉ sửa hồ sơ của mình; thông tin công khai chỉ gồm username, avatar_key.

# 6. Prompt & Output Schema (một lần gọi cho mỗi ảnh)
Dùng structured output (response schema) của Gemini thay vì chỉ dặn trong prompt; server validate lại bằng pydantic. Bounding box lấy theo định dạng box_2d của Gemini (thứ tự [ymin, xmin, ymax, xmax], thang 0–1000); backend chuyển về 0–1 và lấy tâm cho x, y. Định dạng này cần xác nhận lại với phiên bản model dùng thật trong spike Tuần 0.
System: You are an English coach for Vietnamese school students (ages 11-18),
level CEFR A1-B1. Analyze ONE everyday photo. Return JSON only, matching the schema.
{
"topic": "Coffee & Drinks",
"topic_tags": ["cafe", "morning"],
"cefr_level": "A2",
"labels": [                       // 3-5 concrete, visible nouns, no duplicates
{ "name": "coffee cup", "ipa": "/ˈkɒf.i kʌp/", "vi": "tách cà phê",
"accepted_answers": ["cup", "mug"], "cefr": "A1",
"box_2d": [480, 380, 620, 520], "confidence": 0.92 }
],
"descriptions": [                 // 2 short present-simple/continuous sentences
{ "en": "A white mug sits on a small wooden table.", "vi": "..." },
{ "en": "Steam is rising from the hot coffee.", "vi": "..." }
],
"story": { "en": "2-3 short sentences ...", "vi": "..." },
"safety": {
"has_identifiable_faces": false,
"has_personal_info": false,       // plates, name tags, documents, screens
"has_nsfw_or_violence": false,
"is_suitable_for_students": true,
"reasons": []
}
}
Rules:
1. Vocabulary A1-B1 only; natural spoken English; sentences <= 12 words.
2. box_2d must tightly enclose the object; omit any object you are unsure about.
3. Use "accepted_answers" for common synonyms a learner might say.
4. Do not describe or name any person by identity. If unsuitable for students, set
is_suitable_for_students=false and explain in reasons; still return valid JSON.

# 7. Thiết kế giao diện
| Màn hình | Tệp prototype | Ghi chú v1.1 |
|---|---|---|
| Thư viện & Ôn tập | library_review.html | Ghép với review_state; badge "Cần ôn" theo số từ đến hạn. |
| Luyện tập 3 tầng | practice_screen.html | Cần sửa theo mục 3.2: object-contain, bản dịch ẩn mặc định, textContent thay innerHTML, Pointer Events, vùng chạm ≥ 44px. |
| Reflex Mode | reflex_mode.html (mới) | Ẩn nhãn, đếm ngược, đo thời gian, phản hồi, tổng kết phiên. Prototype mô phỏng; bản thật dùng VAD + STT. |
| Prototype đầy đủ (mọi màn hình) | reflex_app.html | Chào mừng, đăng ký + đồng ý phụ huynh, Trang chủ, Khám phá, Thêm ảnh (mô phỏng AI một lần), Xem lại kết quả AI, Luyện tập, Reflex, Thư viện, Hồ sơ. Âm thanh mẫu là mp3 giọng nam trẻ Microsoft trong thư mục audio/, sinh bằng tools/gen_audio.py. |
- Trợ năng: marker dùng thẻ button có aria-label; cỡ chữ tối thiểu 12px; tương phản đạt WCAG AA; có thể thao tác không cần đồng hồ.
- Mobile: ưu tiên Safari iOS và Chrome Android; nút giữ để nói không bật menu ngữ cảnh.

# 8. Spike kỹ thuật (Tuần 0) – tiêu chí đạt
| Câu hỏi | Cách thử | Tiêu chí đạt |
|---|---|---|
| Gemini cho tọa độ đủ chính xác? | 50 ảnh đời thường Việt Nam, một lần gọi/ảnh; so tâm box với nhãn tay | ≥ 85% nhãn lệch ≤ 10% kích thước ảnh |
| JSON hợp lệ không cần thử lại? | Cùng 50 ảnh, structured output | ≥ 98% hợp lệ ngay lần đầu |
| Độ trễ pipeline và chi phí | Đo từ upload đến ready, tính chi phí/ảnh | p50 ≤ 15 giây; chi phí/ảnh ghi nhận để quyết ngưỡng |
| Cờ an toàn có đáng tin? | 20 ảnh có mặt người, biển số, giấy tờ | Phát hiện ≥ 95%; chấp nhận dương tính giả |
| Đo thời điểm bắt đầu nói (VAD) | iPhone Safari và Android tầm trung | Sai số ≤ 150 ms |
| STT trên thiết bị đủ dùng? | Giọng học sinh, từ đơn A1–A2, môi trường lớp học/nhà | Nhận đúng ≥ 85% từ đơn; nếu không dùng STT server |
| Chấm phát âm theo âm vị | Thử một API chuyên dụng với 30 mẫu | Quyết định có đưa vào MVP không |
| Thu âm Safari iOS | Định dạng, quyền mic, tự phát lại | Quy trình thu→tải lên ổn định |

# 9. Lộ trình MVP: Tuần 0 + 6 tuần
| Thời gian | Trọng tâm | Hạng mục |
|---|---|---|
| Tuần 0 | Spike | Chạy bảng mục 8; chốt STT/chấm phát âm; chốt model và chi phí; xác nhận pháp lý về dữ liệu trẻ em. |
| Tuần 1 | Hạ tầng & AI một lần | Supabase schema v1.1 + RLS; Auth + đồng ý phụ huynh; upload → xóa EXIF → hash → dedupe; job Gemini + validate; TTS cache; seed ~100 ảnh hệ thống. |
| Tuần 2 | Luyện tập 3 tầng | Next.js; marker theo tọa độ (object-contain); tab Level 1–2–3 với mở khóa; màn xem lại và chỉnh kết quả AI. |
| Tuần 3 | Âm thanh & Reflex | Thu âm (Pointer Events), VAD, STT; chấm Accuracy; Reflex Mode R1–R3 và tổng kết phiên. |
| Tuần 4 | Thư viện & Ôn tập | Thư viện theo prototype; tìm theo từ vựng; SM-2 theo từ; hàng đợi ôn; Reflex R4. |
| Tuần 5 | An toàn & Khám phá | Kiểm duyệt tự động + hàng chờ; chia sẻ private/lớp/public; Khám phá đọc; báo cáo vi phạm; PWA. |
| Tuần 6 | Pilot | Chạy 1 lớp (~30 học sinh) 2 tuần; đo chỉ số mục 1.3; sửa lỗi; quyết định v1.2. |

# 10. Rủi ro & Câu hỏi mở
| Rủi ro | Tác động | Giảm thiểu |
|---|---|---|
| Dữ liệu và ảnh của trẻ vị thành niên | Pháp lý, uy tín | Đồng ý phụ huynh, private mặc định, xóa EXIF, kiểm duyệt, tối thiểu hóa dữ liệu. |
| AI sai nhãn hoặc tọa độ | Học sai từ, mất niềm tin | Màn xem lại, accepted_answers, confidence thấp thì ẩn nhãn, báo lỗi nhãn. |
| Nội dung dùng chung sai bị lan rộng | Một lỗi ảnh hưởng nhiều người | Báo lỗi nhãn → hàng chờ; sửa nội dung có kiểm duyệt; lưu revision. |
| STT sai với giọng học sinh | Chấm sai, nản chí | Chấp nhận đồng nghĩa, ngưỡng mềm, nút "Tôi đã nói đúng". |
| Trình duyệt iOS hạn chế thu âm/STT | Tính năng cốt lõi không chạy | Spike Tuần 0; phương án STT server. |
| Áp lực đồng hồ làm học sinh lo lắng | Bỏ app | Chế độ ẩn đồng hồ, phản hồi tích cực, phiên ngắn. |

## Câu hỏi cần xác nhận
- Độ tuổi chính xác của pilot (THCS hay THPT) và giáo viên/lớp tham gia.
- Học sinh dùng thiết bị cá nhân hay thiết bị gia đình (ảnh hưởng đăng nhập và quyền riêng tư).
- Có bám theo chủ đề của sách giáo khoa đang dùng (ví dụ danh sách chủ đề từng unit) không.
- Ngân sách AI tối đa mỗi tháng để đặt ngưỡng cho pipeline.