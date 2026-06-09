from pathlib import Path

HTML = Path('/opt/data/as-survey-system/prototype/index.html')


def test_prototype_uses_real_backend_api_config():
    text = HTML.read_text(encoding='utf-8')
    assert 'API_BASE' in text
    assert '/api/auth/as-login' in text
    assert '/api/as/tasks' in text
    assert '/api/admin/surveys/progress' in text


def test_prototype_matches_confirmed_visual_and_photo_decisions():
    text = HTML.read_text(encoding='utf-8')
    assert 'Minimal, lots of whitespace' in text
    assert 'MAX_PHOTOS_PER_QUESTION = 5' in text
    assert 'heavy gradients' not in text.lower().replace('no heavy gradients', '')


def test_survey_headers_have_theme_friendly_accent_colors():
    text = HTML.read_text(encoding='utf-8')
    assert '--accent-ac' in text
    assert '--accent-ref' in text
    assert '--accent-wm' in text
    assert 'class="survey-title-row"' in text
    assert 'surveyAccentClass' in text
    assert 'survey-category-dot' in text
    assert 'survey-title-pill' in text


def test_prototype_has_real_photo_upload_flow():
    text = HTML.read_text(encoding='utf-8')
    assert 'uploadQuestionFiles' in text
    assert '/questions/${q.id}/files' in text
    assert 'type="file"' in text
    assert 'accept="image/*"' in text
    assert 'uploadedFilesByQuestion' in text
    assert 'file_path' in text


def test_prototype_has_as_submitted_image_review_ui():
    text = HTML.read_text(encoding='utf-8')
    assert 'renderSubmittedAnswer' in text
    assert 'renderFilesPreview' in text
    assert '<img' in text


def test_prototype_admin_review_is_status_only_for_scale():
    text = HTML.read_text(encoding='utf-8')
    assert 'loadAdminResponses' in text
    assert '/surveys/${surveyId}/response-status' in text
    assert 'renderAdminASReviewGroup' in text
    assert 'answer_status' in text
    assert 'photo_status' in text
    assert 'renderAdminResponse' not in text
    assert 'responses.map(renderSubmittedAnswer)' not in text


def test_prototype_has_admin_launch_lock_security_ui():
    text = HTML.read_text(encoding='utf-8')
    assert 'adminSecurityBox' in text
    assert '/admin/security/status' in text
    assert '/auth/change-pin' in text
    assert 'changeAdminPin' in text
    assert 'Launch lock' in text
    assert 'newAdminPin' in text


def test_admin_create_survey_web_builder_exists():
    text = HTML.read_text(encoding='utf-8')
    assert 'admin-create-survey' in text
    assert 'Create Survey' in text
    assert 'loadAdminCreateSurvey' in text
    assert 'createSurveyDraft' in text
    assert 'renderAdminBranchPicker' in text
    assert 'addQuestionRow' in text
    assert 'publishCreatedSurvey' in text
    assert '/admin/surveys/${window.adminCreateSurveyId}/publish' in text
    assert '/admin/branches' in text
    assert '/admin/filters' in text


def test_as_task_answer_page_highlights_branch_name():
    text = HTML.read_text(encoding='utf-8')
    assert 'branch-highlight' in text
    assert 'branch-highlight-label' in text
    assert 'branch-highlight-name' in text
    assert 'branch-highlight-meta' in text
    assert 'task.branch_name' in text


def test_as_tasks_completed_surveys_have_clear_section_design():
    text = HTML.read_text(encoding='utf-8')
    assert 'renderCompletedSurveySection' in text
    assert 'completed-surveys-panel' in text
    assert 'completed-surveys-head' in text
    assert 'งานที่ส่งเรียบร้อยแล้ว' in text
    assert 'completed-surveys-count' in text
    assert "renderCompletedSurveyCard(s)" in text


def test_active_as_task_rows_show_original_inline_branch_meta_not_dropdown():
    text = HTML.read_text(encoding='utf-8')
    assert 'renderActiveASTaskRow' in text
    assert '<small>${escapeHtml(t.account)} · ${escapeHtml(t.branch_code)} · Deadline ${fmtDate(t.deadline)}</small>' in text
    assert "active.map(s=>renderSurvey(s,'active'))" in text
    assert "tasks.map(t=>renderActiveASTaskRow(t)).join('')" in text


def test_completed_surveys_show_survey_titles_first_then_branch_names_on_expand():
    text = HTML.read_text(encoding='utf-8')
    assert 'renderCompletedSurveyCard' in text
    assert 'toggleCompletedSurvey' in text
    assert 'activeCompletedSurveyKey' in text
    assert 'completed-survey-toggle' in text
    assert 'completed-survey-branches' in text
    assert 'renderCompletedSurveyBranches' in text
    assert 'กดดูชื่อสาขาที่ส่งแล้ว' in text
    assert "completed.map(s=>renderCompletedSurveyCard(s)).join('')" in text
    assert "tasks.map(t=>renderCompletedASTaskRow(t)).join('')" in text


def test_admin_review_groups_by_region_cards_with_as_rows_not_branch_rows():
    text = HTML.read_text(encoding='utf-8')
    assert 'groupResponsesByRegion' in text
    assert 'displayRegionName' in text
    assert "BANGKOK METROPOLIS" in text
    assert "return 'BKK'" in text
    assert 'renderRegionProgressCards' in text
    assert 'renderRegionProgressCard' in text
    assert 'renderAdminASReviewGroup' in text
    assert 'region-progress-grid' in text
    assert 'region-progress-card' in text
    assert '<th>AS</th><th>Assign</th><th>Submit</th><th>%Progress</th>' in text
    assert 'renderAdminStatusTable(rows)' not in text
    assert '<th>Branch</th><th>AS</th><th>Submit</th>' not in text


def test_admin_review_header_highlights_survey_title():
    text = HTML.read_text(encoding='utf-8')
    assert 'admin-review-survey-highlight' in text
    assert 'admin-review-survey-label' in text
    assert 'admin-review-survey-title' in text
    assert 'admin-review-survey-meta' in text
    assert 'renderAdminReviewSurveyHeader' in text
    assert 'AS Overview' in text


def test_admin_review_as_click_toggles_inline_branch_dropdown():
    text = HTML.read_text(encoding='utf-8')
    assert 'toggleASBranchDropdown' in text
    assert 'renderASBranchDropdownRow' in text
    assert 'activeASDropdownKey' in text
    assert 'branch-dropdown-row' in text
    assert 'branch-dropdown-panel' in text
    assert 'คลิก AS ซ้ำเพื่อปิด dropdown' in text
    assert 'data-as-key="${escapeHtml(key)}"' in text
    assert 'colspan="4"' in text
    assert 'id="asBranchDetailPanel"' not in text


def test_admin_review_as_rows_show_expand_collapse_indicator():
    text = HTML.read_text(encoding='utf-8')
    assert 'as-toggle-indicator' in text
    assert 'aria-label="เปิด/ปิดรายการสาขาของ ${escapeHtml(g.as_code)}"' in text
    assert "window.activeASDropdownKey===key?'▴':'▾'" in text


def test_admin_review_can_filter_only_incomplete_as_groups():
    text = HTML.read_text(encoding='utf-8')
    assert 'renderAdminReviewFilters' in text
    assert 'setAdminReviewFilter' in text
    assert 'adminReviewFilter' in text
    assert 'เฉพาะ AS ที่ยังไม่ครบ' in text
    assert "filter(g=>g.pending>0)" in text
    assert 'ไม่มี AS pending ในมุมมองนี้' in text


def test_admin_review_filter_buttons_show_as_counts():
    text = HTML.read_text(encoding='utf-8')
    assert 'adminReviewFilterCounts' in text
    assert 'filter-count-badge' in text
    assert 'pending_as_count' in text
    assert 'total_as_count' in text
    assert '${counts.total_as_count}' in text
    assert '${counts.pending_as_count}' in text


def test_admin_review_has_summary_cards_and_admin_actions():
    text = HTML.read_text(encoding='utf-8')
    assert 'renderAdminReviewSummaryCards' in text
    assert 'review-summary-grid' in text
    assert 'summary_total_as' in text
    assert 'summary_submitted_as' in text
    assert 'summary_pending_as' in text
    assert 'Completion' in text
    assert 'copyPendingMessage' in text
    assert 'copyPendingList' in text
    assert 'รบกวน AS ที่ยังไม่ได้ส่ง survey' in text


def test_admin_review_pending_message_groups_branches_under_as_code():
    text = HTML.read_text(encoding='utf-8')
    assert 'groupPendingRowsByAS' in text
    assert 'formatPendingGroupMessage' in text
    assert "return `${i+1}. ${asCode}\\n${branches}`" in text
    assert "` - ${r.branch_name||'-'}`" in text
    assert "groups.map(([asCode,rows],i)=>formatPendingGroupMessage(asCode,rows,i)).join('\\n')" in text


def test_admin_review_has_search_export_detail_sort_mobile_and_report_hooks():
    text = HTML.read_text(encoding='utf-8')
    assert 'adminReviewSearch' in text
    assert 'setAdminReviewSearch' in text
    assert 'placeholder="ค้นหา AS / Branch / Region / Account / CAT"' in text
    assert 'exportAdminReviewCsv' in text
    assert 'downloadCsv' in text
    assert 'openAdminReviewDetail' in text
    assert 'admin-review-modal' in text
    assert 'closeAdminReviewDetail' in text
    assert 'adminReviewSort' in text
    assert 'setAdminReviewSort' in text
    assert 'pending_first' in text
    assert 'sticky-review-toolbar' in text
    assert 'renderDailyAdminReport' in text
    assert 'copyDailyAdminReport' in text
    assert 'Daily admin report' in text


def test_admin_management_web_ui_exists_for_users_and_branch_import():
    text = HTML.read_text(encoding='utf-8')
    assert 'admin-management' in text
    assert 'Admin Management' in text
    assert 'loadAdminManagement' in text
    assert 'saveAdminUser' in text
    assert 'resetSelectedAdminUserPin' in text
    assert 'importBranchCsv' in text
    assert '/admin/users' in text
    assert '/admin/branches/import-csv' in text
    assert 'branchCsvFile' in text
