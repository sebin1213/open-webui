<script lang="ts">
	import Modal from '../common/Modal.svelte';
	import XMark from '../icons/XMark.svelte';

	export let show = false;

	// 모달 닫기 옵션 처리
	const handleCloseOption = (option: 'today' | 'close') => {
		const now = new Date();
		
		switch (option) {
			case 'today':
				// 하루동안 보지 않기 - 내일 자정까지 숨김
				const tomorrow = new Date(now);
				tomorrow.setDate(tomorrow.getDate() + 1);
				tomorrow.setHours(0, 0, 0, 0);
				localStorage.setItem('newChatGuidePreference', 'today');
				localStorage.setItem('newChatGuideHideUntil', tomorrow.getTime().toString());
				break;
			case 'close':
				// 단순 닫기 - 다음에 다시 표시
				break;
		}
		
		show = false;
	};
</script>

<Modal bind:show size="lg">
	<div class="modal-content">
		<!-- 헤더 -->
		<div class="modal-header">
			<h2 class="text-xl font-semibold text-gray-900 dark:text-white">
				🚀 DS 챗봇 사용 가이드
			</h2>
			<button
				class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
				on:click={() => handleCloseOption('close')}
			>
				<XMark />
			</button>
		</div>

		<!-- 내용 -->
		<div class="modal-content-body">
				<div class="space-y-4">
					<!-- 링크 섹션 -->
					<div class="link-section">
						<a
							href="https://swing.shinhan.com/ekp/view/board/article/brdAtclViewPopup?atclId=BA90532261171758121350&brdId=BB7502500794235349836&access=&secNtceYn=N"
							target="_blank"
							rel="noopener noreferrer"
							class="link-item"
						>
							<div class="section-icon">📖</div>
							<div class="section-content">
								<span class="link-title">[질문의 기술] 프롬프팅 기초: "좋은 질문 vs 나쁜 질문"</span>
								<span class="link-subtitle">가이드 보러가기</span>
							</div>
							<div class="external-icon">↗</div>
						</a>
					</div>

					<!-- 복리후생 AI 챗봇 사용 가이드 섹션 -->
					<div class="category-section">
						<h2 class="category-title">💭 복리후생 AI 챗봇 사용 가이드</h2>

						<div class="content-section">
							<div class="section-icon">💭</div>
							<div class="section-content">
								<div class="text-sm text-gray-600 dark:text-gray-300 space-y-1">
									<p>복리후생 AI 챗봇은 사내 복리후생 제도 전반에 대한 정보를 쉽고 빠르게 안내해드립니다.</p><br>
									<p>다만 아래 항복들은 현재 준비중이므로, 관련 문의는 각 담당자에게 직접 문의 해주세요.</p>
									<p class="ml-4">• 교육관련 : 100H, 러닝크루, 사외교육, 리부팅투어 등</p>
									<p class="ml-4">• 인사관련 : Shiftee(근태), 승진 등</p>
									<p>이 부분들은 순차적으로 오픈될 예정이니 조금만 기다려 주세요.😄</p><br>
									<p class="mt-2 text-blue-600 dark:text-blue-400">복리후생 AI 챗봇은 현재 시점 기준의 실시간 계산형 질문에는 답변이 어렵습니다.</p>
									<p>ex. 오늘 기준 휴가 생성개수❌, 현재 보유한 연성소 쿠폰 개수❌</p><br>
									<p>⚙️ 향후 단계적으로 기능을 확대해 더욱 정확하고 풍부한 정보를 제공할 예정입니다.</p>
								</div>
							</div>
						</div>
					</div>

					<!-- 개인화 챗봇 사용 가이드 섹션 -->
					<div class="category-section">
						<h2 class="category-title">💬 개인화 챗봇 사용 가이드</h2>

						<!-- 채팅 가이드 -->
					<div class="content-section">
						<div class="section-icon">💬</div>
						<div class="section-content">
							<h3 class="font-medium text-gray-900 dark:text-white mb-2"><strong>채팅</strong></h3>
							<div class="text-sm text-gray-600 dark:text-gray-300 space-y-1">
								<p>일반적인 지식과 업무 도움에 대한 질의 응답이 가능합니다.</p>
								<p>ex. 오늘 점심 메뉴를 추천해줘</p>
								<p class="mt-2 text-blue-600 dark:text-blue-400">동일 채팅방에서 최대 10번의 최근 채팅을 기억하고 문맥을 이어 갑니다</p>
								<p class="mt-2 text-blue-600 dark:text-blue-400">웹 검색을 통한 최신 정보는 확인이 불가능합니다.</p>
								<p class="mt-2 text-blue-600 dark:text-blue-400">회사 내규와 같은 특정 지식 정보 검색은 불가능합니다.</p>
								<p>ex. 오늘 날씨 어때?❌ 우리 회사 내규를 알려줘❌</p>
								<p class="mt-2">오류 발생 시 '새 채팅'으로 새롭게 시작 필요</p>
							</div>
						</div>
					</div>

					<!-- 팁 -->
					<div class="tip-box">
						<div class="tip-content">
							<div class="section-icon" style="font-size: 1.25rem;">💡</div>
							<div class="section-content">
								<h4 class="font-medium text-blue-900 dark:text-blue-100 mb-2">PPT 생성</h4>
								<p class="text-sm text-blue-800 dark:text-blue-200 multiline-text">
									이제 AI 답변을 피피티로 만들 수 있습니다! 최대 슬라이드 20장
									답변 메시지 우측 하단 <img src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB4PSIyIiB5PSIyIiB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHJ4PSIzIiBmaWxsPSIjRDI0NzI2Ii8+CiAgPHJlY3QgeD0iNSIgeT0iNyIgd2lkdGg9IjEyIiBoZWlnaHQ9IjgiIHJ4PSIxIiBmaWxsPSJ3aGl0ZSIvPgogIDxwYXRoIGQ9Ik03IDloNXYySDdWOW0wIDNoOHYySDd2LTJaIiBmaWxsPSIjRDI0NzI2Ii8+CiAgPGNpcmNsZSBjeD0iMTYuNSIgY3k9IjE2LjUiIHI9IjMuNSIgZmlsbD0id2hpdGUiLz4KICA8cGF0aCBkPSJNMTYuNSAxM3YzLjVIMjBBMy41IDMuNSAwIDAgMCAxNi41IDEzeiIgZmlsbD0iI0QyNDcyNiIvPgo8L3N2Zz4=" alt="PPT 생성" class="inline-icon"> ppt 생성 버튼을 눌러보세요!
									ppt 내용을 잘 만들 수 있는 질문을 할수록 완성도가 높아집니다!
								</p>
							</div>
						</div>
					</div>

					<!-- 이미지 가이드 -->
					<div class="content-section">
						<div class="section-icon">🖼️</div>
						<div class="section-content">
							<h3 class="font-medium text-gray-900 dark:text-white mb-2"><strong>이미지</strong></h3>
							<div class="text-sm text-gray-600 dark:text-gray-300 space-y-1">
								<p>파일 업로드 버튼, 드래그 앤 드롭, 복사/붙여넣기를 통해 이미지를 업로드할 수 있습니다.</p>
								<p>ex. 이미지 안 내용을 정리해줘</p>
								<p class="mt-2 text-blue-600 dark:text-blue-400">한 번에 하나의 이미지만 인식 가능합니다.</p>
							</div>
						</div>
					</div>

					<!-- 파일 업로드 가이드 -->
					<div class="content-section">
						<div class="section-icon">📎</div>
						<div class="section-content">
							<h3 class="font-medium text-gray-900 dark:text-white mb-2"><strong>파일</strong></h3>
							<div class="text-sm text-gray-600 dark:text-gray-300 space-y-1">
								<p>파일 업로드 버튼, 드래그 앤 드롭, 복사/붙여넣기를 통해 파일을 업로드할 수 있습니다.</p>
								<p>ex. 파일 내용을 요약해줘</p>
								<p class="mt-2">지원 형식: PDF, DOCX, DOC, PPTX, PPT, XLSX</p>
								<p>단일 채팅에서 파일 최대 개수 3개, 단일 채팅에서 파일 최대 크기 20MB(파일 1개당)</p>
								<p class="text-blue-600 dark:text-blue-400">DRM이 해제된 파일만 가능</p>
								<p>내용이 빈 파일은 사용 불가능</p>
								<p>파일 업로드 이후 채팅을 입력해 사용을 부탁드립니다.(질문이 없을 경우 오류 발생)</p>
							</div>
						</div>
					</div>

						<!-- 팁 -->
						<div class="tip-box">
							<div class="tip-content">
								<div class="section-icon" style="font-size: 1.25rem;">💡</div>
								<div class="section-content">
									<h4 class="font-medium text-blue-900 dark:text-blue-100 mb-2">사용 팁</h4>
									<p class="text-sm text-blue-800 dark:text-blue-200 multiline-text">
										복잡한 문서의 경우 먼저 "이 문서의 주요 내용을 요약해주세요"라고 질문해보세요.
										문서 구조를 파악한 후 세부적인 질문을 하면 더 나은 결과를 얻을 수 있습니다.
									</p>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>

		<!-- 푸터 버튼들 -->
		<div class="modal-footer">
			<div class="button-group">
				<button
					class="button"
					on:click={() => handleCloseOption('today')}
				>
						하루동안 보지 않기
					</button>
				</div>
			<button
				class="primary-button"
				on:click={() => handleCloseOption('close')}
			>
					시작하기
				</button>
		</div>
	</div>
</Modal>

<style>
	/* 엣지 구버전 호환성을 위한 CSS */
	.modal-content {
		display: -webkit-box;
		display: -ms-flexbox;
		display: flex;
		-webkit-box-orient: vertical;
		-webkit-box-direction: normal;
		-ms-flex-direction: column;
		flex-direction: column;
		max-height: 90vh;
		max-height: 90vh; /* IE fallback */
	}
	
	.modal-header {
		display: -webkit-box;
		display: -ms-flexbox;
		display: flex;
		-webkit-box-align: center;
		-ms-flex-align: center;
		align-items: center;
		-webkit-box-pack: justify;
		-ms-flex-pack: justify;
		justify-content: space-between;
		padding: 1.5rem;
		border-bottom: 1px solid #e5e7eb;
	}
	
	.modal-content-body {
		padding: 1.5rem;
		overflow-y: auto;
		-webkit-overflow-scrolling: touch; /* iOS 스크롤 개선 */
	}
	
	.content-section {
		display: -webkit-box;
		display: -ms-flexbox;
		display: flex;
		-webkit-box-align: start;
		-ms-flex-align: start;
		align-items: flex-start;
		margin-bottom: 1rem;
	}
	
	.section-icon {
		font-size: 1.5rem;
		margin-right: 0.75rem;
		-webkit-flex-shrink: 0;
		-ms-flex-negative: 0;
		flex-shrink: 0;
	}
	
	.section-content {
		-webkit-box-flex: 1;
		-ms-flex: 1;
		flex: 1;
	}
	
	.modal-footer {
		display: -webkit-box;
		display: -ms-flexbox;
		display: flex;
		-webkit-box-align: center;
		-ms-flex-align: center;
		align-items: center;
		-webkit-box-pack: justify;
		-ms-flex-pack: justify;
		justify-content: space-between;
		padding: 1.5rem;
		border-top: 1px solid #e5e7eb;
	}
	
	.button-group {
		display: -webkit-box;
		display: -ms-flexbox;
		display: flex;
	}
	
	.button {
		padding: 0.5rem 1rem;
		margin-right: 0.75rem;
		font-size: 0.875rem;
		border: none;
		background: transparent;
		cursor: pointer;
		text-decoration: underline;
		color: #6b7280;
		-webkit-transition: color 0.2s ease;
		-moz-transition: color 0.2s ease;
		-ms-transition: color 0.2s ease;
		-o-transition: color 0.2s ease;
		transition: color 0.2s ease;
	}
	
	.button:hover {
		color: #374151;
	}
	
	.primary-button {
		padding: 0.5rem 1.5rem;
		background-color: #3b82f6;
		color: white;
		border: none;
		border-radius: 0.5rem;
		font-weight: 500;
		cursor: pointer;
		-webkit-transition: background-color 0.2s ease;
		-moz-transition: background-color 0.2s ease;
		-ms-transition: background-color 0.2s ease;
		-o-transition: background-color 0.2s ease;
		transition: background-color 0.2s ease;
	}
	
	.primary-button:hover {
		background-color: #2563eb;
	}
	
	.tip-box {
		background-color: #eff6ff;
		border-radius: 0.5rem;
		padding: 1rem;
		margin-top: 1rem;
	}
	
	.tip-content {
		display: -webkit-box;
		display: -ms-flexbox;
		display: flex;
		-webkit-box-align: start;
		-ms-flex-align: start;
		align-items: flex-start;
	}
	
	/* 다크모드 지원 */
	@media (prefers-color-scheme: dark) {
		.modal-header {
			border-bottom-color: #374151;
		}
		
		.modal-footer {
			border-top-color: #374151;
		}
		
		.button {
			color: #9ca3af;
		}
		
		.button:hover {
			color: #d1d5db;
		}
		
		.tip-box {
			background-color: rgba(30, 58, 138, 0.2);
		}
	}
	
	/* 링크 스타일 */
	.link-section {
		margin-bottom: 1rem;
	}
	
	.link-item {
		display: -webkit-box;
		display: -ms-flexbox;
		display: flex;
		-webkit-box-align: center;
		-ms-flex-align: center;
		align-items: center;
		-webkit-box-pack: justify;
		-ms-flex-pack: justify;
		justify-content: space-between;
		padding: 1rem;
		background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
		border: none;
		border-radius: 0.75rem;
		text-decoration: none;
		color: white;
		cursor: pointer;
		-webkit-transition: all 0.3s ease;
		-moz-transition: all 0.3s ease;
		-ms-transition: all 0.3s ease;
		-o-transition: all 0.3s ease;
		transition: all 0.3s ease;
		box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
	}
	
	.link-item:hover {
		background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
		transform: translateY(-2px);
		box-shadow: 0 8px 20px rgba(59, 130, 246, 0.3);
	}
	
	.section-content {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	
	.link-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: white;
		line-height: 1.3;
	}
	
	.link-subtitle {
		font-size: 0.75rem;
		color: rgba(255, 255, 255, 0.8);
		font-weight: 400;
	}
	
	.external-icon {
		font-size: 1.25rem;
		color: white;
		opacity: 0.8;
		-webkit-transition: all 0.2s ease;
		-moz-transition: all 0.2s ease;
		-ms-transition: all 0.2s ease;
		-o-transition: all 0.2s ease;
		transition: all 0.2s ease;
	}
	
	.link-item:hover .external-icon {
		opacity: 1;
		transform: translate(2px, -2px);
	}
	
	/* 다크모드 링크 스타일 */
	@media (prefers-color-scheme: dark) {
		.link-item {
			background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
			box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
		}
		
		.link-item:hover {
			background: linear-gradient(135deg, #1d4ed8 0%, #1e3a8a 100%);
			box-shadow: 0 8px 20px rgba(37, 99, 235, 0.4);
		}
	}

	/* 줄바꿈 처리 */
	.multiline-text {
		white-space: pre-line;
		line-height: 1.5;
	}

	/* 인라인 아이콘 스타일 */
	.inline-icon {
		display: inline-block;
		width: 16px;
		height: 16px;
		vertical-align: middle;
		margin: 0 2px;
	}

	/* 카테고리 섹션 스타일 */
	.category-section {
		border: 2px solid #e5e7eb;
		border-radius: 0.75rem;
		padding: 1.25rem;
		margin-bottom: 1.5rem;
		background-color: #f9fafb;
	}

	.category-title {
		font-size: 1.125rem;
		font-weight: 700;
		color: #1f2937;
		margin-bottom: 1rem;
		padding-bottom: 0.75rem;
		border-bottom: 2px solid #d1d5db;
	}

	@media (prefers-color-scheme: dark) {
		.category-section {
			border-color: #4b5563;
			background-color: rgba(31, 41, 55, 0.3);
		}

		.category-title {
			color: #f3f4f6;
			border-bottom-color: #4b5563;
		}
	}

	/* IE11 호환성 */
	@media screen and (-ms-high-contrast: active), (-ms-high-contrast: none) {
		.modal-content {
			display: -ms-flexbox;
			-ms-flex-direction: column;
			flex-direction: column;
		}
		
		.modal-header, .content-section, .modal-footer {
			display: -ms-flexbox;
		}
		
		.section-content {
			-ms-flex: 1;
			flex: 1;
		}
		
		.link-item {
			display: -ms-flexbox;
		}
		
		/* IE11에서는 white-space: pre-line 대신 */
		.multiline-text {
			white-space: pre;
		}
	}
</style>
