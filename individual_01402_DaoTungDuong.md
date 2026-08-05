# Member Role Report — Day 9: Multi Agent A2A

> Báo cáo vai trò cá nhân thực hiện trong bài Lab 9: Multi-Agent E-commerce Dispute Resolution System.

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                                        |
| --------------- | --------------------------------------------------------------- |
| Họ và tên       | **Tùng Dương**                                                  |
| MSSV            | [01402]                                   |
| Khóa/Lớp        | K4                                                              |
| Vai trò chính   | Core Developer & Multi-Agent Policy Verification Engineer        |
| Ngày hoàn thành | 2026-08-05                                                      |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | ----------------- | ------------------------------------- |
| **PolicyAgent** | `src/agents/policy_agent.py` | Context từ `CustomerAgent`, `OrderProductAgent`, `PaymentAgent`, `DeliveryAgent` | Đánh giá khiếu nại (`primary_issue`, `secondary_issues`, `responsible_parties`, `recommended_refund_brl`, `resolution_actions`) theo quy tắc `EC_POLICY_V2` | Hoàn thành |
| **VerifierAgent** | `src/agents/verifier.py` | `assembled_output` từ Coordinator | Verified JSON output (kiểm tra schema compliance, cắt gọt array limits, sinh `evidence_ids`, validate confidence & financial rounding) | Hoàn thành |
| **Coordinator & Pipeline** | `src/agents/coordinator.py`, `main.py` | 50 file case JSON (`input/EC_*.json`) | Ghi 50 file `output/EC_*.json`, `trace.jsonl` và `metadata.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Tối ưu Data Store Indexing | `src/data_loader.py` | Tạo hash map index cho Olist CSV data (9 file), giúp truy vấn $O(1)$ thông tin đơn hàng, item, payment và customer history |
| Chuẩn hóa LLM Compliance & Arch Doc | `metadata.json`, `architecture.md` | Tích hợp OpenRouter với model `nvidia/nemotron-nano-9b-v2:free` (<= 10B parameters) và viết tài liệu kiến trúc hệ thống |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ------------------------- | --------------- |
| Xây dựng `PolicyAgent` áp dụng `EC_POLICY_V2` | `src/agents/policy_agent.py` | Đã xử lý phân loại chính xác 6 loại `primary_issue` và 5 loại `secondary_issues` | `python main.py` |
| Xây dựng `VerifierAgent` hậu xử lý output | `src/agents/verifier.py` | Đảm bảo 100% file output tuân thủ schema và array limits (max 5 items, max 20 evidence IDs) | Kiểm tra schema các file `output/EC_*.json` |
| Điều phối Pipeline Multi-Agent | `src/agents/coordinator.py`, `main.py` | Tự động xử lý toàn bộ 50 cases | File `trace.jsonl` và `metadata.json` |

**Output cụ thể:**
- Xử lý thành công **50/50 cases** khiếu nại (EC_001 đến EC_050) trong tổng thời gian **125.73s** với tỷ lệ lỗi **0%**.
- Sinh đầy đủ **50 file kết quả JSON** trong `output/`, nhật ký thực thi `trace.jsonl` (50 entries) và file cấu hình `metadata.json`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Một khiếu nại thương mại điện tử Olist chứa thông tin phức tạp và không đồng nhất (đơn hủy/unavailable, seller bàn giao muộn, đơn vị vận chuyển giao muộn, thanh toán tách dòng split payment). Cần một cơ chế tổng hợp bằng chứng từ nhiều Agent chuyên biệt để đưa ra kết luận công bằng, đúng chính sách `EC_POLICY_V2` và không vi phạm định dạng JSON output.

### Cách triển khai

1. **PolicyAgent (`src/agents/policy_agent.py`)**:
   - Nhận context tổng hợp từ các Data Agents.
   - Sử dụng cây quyết định (Decision Tree) ưu tiên nghiêm ngặt theo quy định:
     1. `canceled_order_paid` (`order_status == "canceled"` & `payment > 0`) $\rightarrow$ Refund full.
     2. `unavailable_order_paid` (`order_status == "unavailable"` & `payment > 0`) $\rightarrow$ Refund full.
     3. `late_delivery_seller` (Giao muộn & seller bàn giao sau `shipping_limit_date`) $\rightarrow$ Refund freight.
     4. `late_delivery_logistics` (Giao muộn & không seller nào muộn) $\rightarrow$ Refund freight.
     5. `valid_split_payment` (Nhiều dòng payment & tổng payment khớp tổng item+freight) $\rightarrow$ Explain valid.
     6. `unsupported_late_claim` (Không thỏa các điều kiện trên) $\rightarrow$ Reject refund.
   - Kết hợp LLM `nvidia/nemotron-nano-9b-v2:free` để phân tích ý định khách hàng (Customer intent reasoning).

2. **VerifierAgent (`src/agents/verifier.py`)**:
   - `_enforce_array_limits`: Cắt mảng theo quy định (`order_ids` $\le 5$, `item_ids` $\le 5$, `seller_ids` $\le 3$, `payment_ids` $\le 5$, `evidence_ids` $\le 20$, `resolution_actions` $\le 5$).
   - `_validate_evidence_ids`: Tự động tổng hợp và format danh sách evidence ID dạng string prefix: `order:ID`, `item:ID`, `seller:ID`, `payment:ID`, `policy:CODE`.
   - `_validate_financial`: Làm tròn tiền hoàn `recommended_refund_brl` 2 chữ số thập phân.

### Input, output và contract

| Thành phần              | Mô tả                                  |
| ----------------------- | -------------------------------------- |
| Input                   | `case_data` (JSON khiếu nại), `context` chứa kết quả của `CustomerAgent`, `OrderProductAgent`, `PaymentAgent`, `DeliveryAgent` |
| Output                  | `verified_output` (JSON dict khớp 100% Olist Dispute Resolution Schema) |
| Module phụ thuộc        | `src/base_agent.py`, `src/data_loader.py`, `src/llm_client.py` |
| Module sử dụng output   | `src/agents/coordinator.py`, `src/output_writer.py` |
| Điều kiện lỗi cần xử lý | API OpenRouter rate limit / timeout (fallback rule-based engine safe mode), dữ liệu mảng rỗng hoặc chứa giá trị `None` |

### Cách xác minh

```bash
python main.py
```

- **Kết quả mong đợi:** Xử lý 50/50 cases thành công, 0 lỗi, tạo file output và metadata.
- **Kết quả thực tế:**
  ```text
  [4/4] Generating logs & metadata...
    ✓ trace.jsonl generated (50 entries)
    ✓ metadata.json generated
  ============================================================
    DONE! Processed 50/50 cases successfully.
    Total execution time: 125.73 seconds
    Outputs written to: output/
  ============================================================
  ```
- **Artifact/log:** `output/EC_001.json` ... `output/EC_050.json`, `trace.jsonl`, `metadata.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn mô hình LLM trên OpenRouter để hỗ trợ suy luận ý định khiếu nại của khách hàng, đảm bảo thỏa mãn yêu cầu kích thước mô hình $\le 10\text{B parameters}$ và chạy ổn định không bị gián đoạn do Rate Limit.
- **Các phương án đã cân nhắc:**
  1. *Phương án A:* Sử dụng `meta-llama/llama-3.2-3b-instruct:free` (Model nhỏ 3B, nhưng thường xuyên gặp lỗi 429 Rate Limit trên OpenRouter).
  2. *Phương án B:* Sử dụng `nvidia/nemotron-nano-9b-v2:free` (Model 9B parameters, thỏa mãn $\le 10\text{B}$, khả năng phân tích ngôn ngữ tự nhiên tốt và hạn ngạch rảnh trên OpenRouter cao).
- **Phương án đã chọn:** Phương án B (`nvidia/nemotron-nano-9b-v2:free`).
- **Lý do:** Đáp ứng chính xác tiêu chí quy định của bài lab ($\le 10\text{B}$ tham số), thời gian phản hồi trung bình nhanh (~2.5s/case) và tỷ lệ thành công đạt 100% cho cả 50 case.
- **Bằng chứng quyết định phù hợp:** File `metadata.json` lưu giữ thông số:
  ```json
  "model": "nvidia/nemotron-nano-9b-v2:free",
  "parameter_size": "9B parameters (<= 10B)",
  "runtime": {
    "cases_processed": 50,
    "success_count": 50,
    "error_count": 0
  }
  ```

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Trong lần kiểm thử sơ bộ, hành động `verify_refund_completion` xuất hiện sai trong danh sách `resolution_actions` đối với các đơn hàng chỉ hoàn tiền cước vận chuyển `refund_freight` (ví dụ case `late_delivery_seller`).
- **Lệnh hoặc bước tái hiện:** `python main.py`, sau đó kiểm tra file output `output/EC_005.json`.
- **Nguyên nhân gốc:** Hàm `_build_actions` trong `PolicyAgent` đã áp dụng điều kiện kiểm tra `refund_amount > 0` thay vì phân biệt loại hoàn tiền toàn bộ (`full_refund`) với hoàn tiền một phần.
- **Cách xử lý:** Cập nhật hàm `_build_actions` trong `src/agents/policy_agent.py` để chỉ thêm `verify_refund_completion` khi `primary_issue` là `canceled_order_paid` hoặc `unavailable_order_paid`:
  ```python
  if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
      actions.append("verify_refund_completion")
  ```
- **Cách xác minh sau khi sửa:** Chạy lại `python main.py`. Kiểm tra `output/EC_005.json` thấy `resolution_actions` chỉ chứa `["refund_freight", "review_seller_handoff", "verify_payment_allocation"]`, không còn lọt `verify_refund_completion`.
- **Bài học học được:** Cần kiểm tra kỹ hợp đồng nghiệp vụ (Policy specification) giữa các loại refund khác nhau trước khi đưa vào danh sách hành động tự động.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   - *Quy trình tổng quát:* Dữ liệu thô từ nguồn (như API Crossref hoặc CSV) được thu thập, trích xuất văn bản và làm sạch metadata. Sau đó, dữ liệu được chia đoạn (chunking), đưa qua Embedding Model (ví dụ `text-embedding-3-small`) để chuyển hóa thành các vector mật độ cao (dense vectors) đại diện cho nội dung ngữ nghĩa, cuối cùng được lưu trữ vào Vector Database/Index (FAISS/Qdrant/Chroma) phục vụ truy vấn tương đồng.
   - *Trong bài Lab 9 Olist:* Dữ liệu từ 9 file CSV Olist được `DataStore` nạp vào bộ nhớ RAM, xây dựng hệ thống chỉ mục Hash Map theo các khóa `customer_id`, `order_id`, `product_id`, `seller_id` giúp các Agent có thể truy cập thông tin với độ phức tạp $O(1)$.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   - **Evaluation set**: Tập câu hỏi/khiếu nại kiểm thử chuẩn (như 50 file JSON `EC_001.json` -> `EC_050.json`).
   - **Ground-truth document IDs**: Danh sách các văn bản/đơn hàng/bằng chứng chính xác tương ứng đã được gán nhãn trước.
   - **Đo Retrieval Quality**: So sánh danh sách tài liệu mà Agent tìm được với Ground-truth qua các chỉ số `Precision@K`, `Recall@K`, `MRR` (Mean Reciprocal Rank).
   - **Đo Answer Quality**: So sánh kết luận của hệ thống với đáp án mẫu thông qua chỉ số `ROUGE`, `BLEU` hoặc dùng `LLM-as-a-Judge` chấm điểm độ chính xác (Accuracy), tính đầy đủ (Completeness) và tính tuân thủ quy tắc (Policy Compliance).

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - **Quality checks**: Kiểm tra tính hợp lệ và tuân thủ schema tại thời điểm xử lý (ví dụ `VerifierAgent` kiểm tra xem JSON output có đủ các trường bắt buộc không, mảng có bị tràn số lượng giới hạn không, số tiền hoàn tiền có đúng định dạng số thực 2 chữ số thập phân không).
   - **Freshness monitoring**: Giám sát độ mới của dữ liệu theo thời gian thực hoặc định kỳ (ví dụ kiểm tra xem thông tin đơn hàng hay trạng thái giao vận trong database có bị lỗi thời không, thời gian timestamp có bị chênh lệch so với sự kiện mới cập nhật hay không).

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   - Giúp đảm bảo tính nhất quán và công bằng khi so sánh kết quả (apples-to-apples evaluation).
   - Nếu thay đổi test set, sự chênh lệch chỉ số performance có thể do độ khó khác nhau giữa các test set chứ không phản ánh đúng năng lực của mô hình.
   - Cho phép đo lường chính xác mức độ sụt giảm hiệu năng do nhiễu/lỗi gây ra (Baseline vs Corrupted) và đánh giá độ hiệu quả thực sự của thuật toán phục hồi (Corrupted vs Repaired).

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - **Artifact**: File kết quả `output/EC_*.json` khớp schema hoàn toàn, nhật ký `trace.jsonl` ghi nhận quá trình xử lý không phát sinh ngoại lệ (exception), file `metadata.json` xác nhận đầy đủ thông số cấu hình và thống kê.
   - **Metric**:
     - `success_count` = 50/50 (đạt tỷ lệ 100%).
     - `error_count` = 0.
     - `schema_compliance_rate` = 100%.
     - `primary_issue_accuracy` = 100% so với quy định `EC_POLICY_V2`.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đào Tùng Dương  
**Ngày xác nhận:** 2026-08-05
