<script lang="ts">
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { downloadDatabase, downloadLiteLLMConfig } from '$lib/apis/utils';
	import { getUsageStats, exportUsageStats, getFileStorageStats, previewDataCleanup, executeDataCleanup } from '$lib/apis/statistics';
	import { onMount, getContext } from 'svelte';
	import { config, user } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import { getAllUserChats } from '$lib/apis/chats';
	import { getAllUsers } from '$lib/apis/users';
	import { exportConfig, importConfig } from '$lib/apis/configs';

	const i18n = getContext('i18n');

	export let saveHandler: Function;

	// 통계 관련 변수들
	let startDate = '';
	let endDate = '';
	let startTime = '00:00';
	let endTime = '23:59';
	let filterTeam: string = '';
	let filterHQ: string = '';
	let filterDivision: string = '';
	let statsData = null;
	let loading = false;
	let currentPage = 1;
	const pageSize = 10;

	// 파일 스토리지 분석 관련 변수들
	let storageStats = null;
	let storageLoading = false;
	let activeTab = 'usage'; // 'usage', 'storage', 또는 'cleanup'

	// 데이터 삭제 관련 변수들
	let cleanupCutoffDate = '';
	let cleanupCutoffTime = '23:59:59';
	let deleteFiles = true;
	let deleteVectors = true;
	let deleteDbRecords = true;
	let cleanupPreview = null;
	let cleanupResult = null;
	let cleanupLoading = false;
	let showCleanupConfirm = false;
	let confirmPassword = '';

	const exportAllUserChats = async () => {
		let blob = new Blob([JSON.stringify(await getAllUserChats(localStorage.token))], {
			type: 'application/json'
		});
		saveAs(blob, `all-chats-export-${Date.now()}.json`);
	};

	const fetchUsageStats = async () => {
		if (!startDate || !endDate) {
			toast.error('시작일과 종료일을 입력해주세요.');
			return;
		}
		
		loading = true;
		try {
			statsData = await getUsageStats(localStorage.token, startDate, endDate, currentPage, pageSize, {
				startTime,
				endTime,
				team: filterTeam || undefined,
				headquarters: filterHQ || undefined,
				division: filterDivision || undefined,
			});
		} catch (error) {
			toast.error(`통계 조회 실패: ${error.detail || error.message}`);
			statsData = null;
		} finally {
			loading = false;
		}
	};

	const exportStats = async () => {
		if (!startDate || !endDate) {
			toast.error('시작일과 종료일을 입력해주세요.');
			return;
		}
		
		try {
			await exportUsageStats(localStorage.token, startDate, endDate, {
				startTime,
				endTime,
				team: filterTeam || undefined,
				headquarters: filterHQ || undefined,
				division: filterDivision || undefined,
			});
			toast.success('통계 파일이 다운로드되었습니다.');
		} catch (error) {
			toast.error(`통계 익스포트 실패: ${error.detail || error.message}`);
		}
	};

	const changePage = (page: number) => {
		currentPage = page;
		fetchUsageStats();
	};

	const fetchFileStorageStats = async () => {
		storageLoading = true;
		try {
			storageStats = await getFileStorageStats(localStorage.token);
		} catch (error) {
			toast.error(`파일 스토리지 통계 조회 실패: ${error.detail || error.message}`);
			storageStats = null;
		} finally {
			storageLoading = false;
		}
	};

	const exportUsers = async () => {
		const users = await getAllUsers(localStorage.token);

		const headers = ['id', 'name', 'email', 'role'];

		const csv = [
			headers.join(','),
			...users.users.map((user) => {
				return headers
					.map((header) => {
						if (user[header] === null || user[header] === undefined) {
							return '';
						}
						return `"${String(user[header]).replace(/"/g, '""')}"`;
					})
					.join(',');
			})
		].join('\n');

		const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
		saveAs(blob, 'users.csv');
	};

	onMount(async () => {
		// 오늘 날짜로 기본값 설정 (최근 7일)
		const today = new Date();
		const lastWeek = new Date(today);
		lastWeek.setDate(today.getDate() - 6);

		endDate = today.toISOString().split('T')[0];
		startDate = lastWeek.toISOString().split('T')[0];

		// 파일 스토리지 분석은 현재 현황만 조회 (기간별 분석 없음)

		// 데이터 삭제 기본값 (일주일 전)
		cleanupCutoffDate = lastWeek.toISOString().split('T')[0];

	});

	const fetchCleanupPreview = async () => {
		if (!cleanupCutoffDate) {
			toast.error('삭제 기준 날짜를 입력해주세요.');
			return;
		}

		cleanupLoading = true;
		try {
			cleanupPreview = await previewDataCleanup(
				localStorage.token,
				cleanupCutoffDate,
				cleanupCutoffTime,
				{
					deleteFiles,
					deleteVectors,
					deleteDbRecords
				}
			);
		} catch (error) {
			toast.error(`삭제 미리보기 실패: ${error.detail || error.message}`);
			cleanupPreview = null;
		} finally {
			cleanupLoading = false;
		}
	};

	const executeCleanup = async (dryRun = false) => {
		if (!cleanupCutoffDate) {
			toast.error('삭제 기준 날짜를 입력해주세요.');
			return;
		}

		if (!dryRun) {
			if (!confirmPassword || confirmPassword.trim() === '') {
				toast.error('현재 비밀번호를 입력해주세요.');
				return;
			}
		}

		cleanupLoading = true;
		try {
			cleanupResult = await executeDataCleanup(
				localStorage.token,
				cleanupCutoffDate,
				cleanupCutoffTime,
				{
					deleteFiles,
					deleteVectors,
					deleteDbRecords,
					dryRun,
					...(dryRun ? {} : { confirmPassword })
				}
			);

			if (!dryRun) {
				toast.success('데이터 삭제가 완료되었습니다.');
				showCleanupConfirm = false;
			}
		} catch (error) {
			toast.error(`데이터 삭제 실패: ${error.detail || error.message}`);
		} finally {
			cleanupLoading = false;
		}
	};
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={async () => {
		saveHandler();
	}}
>
	<div class=" space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		<div>
			<div class=" mb-2 text-sm font-medium">{$i18n.t('Database')}</div>

			<input
				id="config-json-input"
				hidden
				type="file"
				accept=".json"
				on:change={(e) => {
					const file = e.target.files[0];
					const reader = new FileReader();

					reader.onload = async (e) => {
						const res = await importConfig(localStorage.token, JSON.parse(e.target.result)).catch(
							(error) => {
								toast.error(`${error}`);
							}
						);

						if (res) {
							toast.success($i18n.t('Config imported successfully'));
						}
						e.target.value = null;
					};

					reader.readAsText(file);
				}}
			/>

			<button
				type="button"
				class=" flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
				on:click={async () => {
					document.getElementById('config-json-input').click();
				}}
			>
				<div class=" self-center mr-3">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
						<path
							fill-rule="evenodd"
							d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
							clip-rule="evenodd"
						/>
					</svg>
				</div>
				<div class=" self-center text-sm font-medium">
					{$i18n.t('Import Config from JSON File')}
				</div>
			</button>

			<button
				type="button"
				class=" flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
				on:click={async () => {
					const config = await exportConfig(localStorage.token);
					const blob = new Blob([JSON.stringify(config)], {
						type: 'application/json'
					});
					saveAs(blob, `config-${Date.now()}.json`);
				}}
			>
				<div class=" self-center mr-3">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
						<path
							fill-rule="evenodd"
							d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
							clip-rule="evenodd"
						/>
					</svg>
				</div>
				<div class=" self-center text-sm font-medium">
					{$i18n.t('Export Config to JSON File')}
				</div>
			</button>

			<hr class="border-gray-50 dark:border-gray-850 my-1" />

			{#if $config?.features.enable_admin_export ?? true}
				<button
					type="button"
					class="flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					on:click={() => downloadDatabase(localStorage.token).catch((error) => toast.error(`${error}`))}
				>
					<div class="self-center mr-3">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-4 h-4">
							<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
							<path fill-rule="evenodd" d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z" clip-rule="evenodd" />
						</svg>
					</div>
					<div class="self-center text-sm font-medium">{$i18n.t('Download Database')}</div>
				</button>

				<button
					type="button"
					class="flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					on:click={exportAllUserChats}
				>
					<div class="self-center mr-3">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-4 h-4">
							<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
							<path fill-rule="evenodd" d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z" clip-rule="evenodd" />
						</svg>
					</div>
					<div class="self-center text-sm font-medium">{$i18n.t('Export All Chats (All Users)')}</div>
				</button>
			{/if}

			<hr class="border-gray-100 dark:border-gray-850 my-1" />

			<!-- 탭 네비게이션 -->
			<div class="flex space-x-1 mb-4">
				<button
					type="button"
					class="px-3 py-2 text-sm rounded-md transition {activeTab === 'usage'
						? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
						: 'text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200'}"
					on:click={() => (activeTab = 'usage')}
				>
					사용자 통계
				</button>
				<button
					type="button"
					class="px-3 py-2 text-sm rounded-md transition {activeTab === 'storage'
						? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
						: 'text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200'}"
					on:click={() => (activeTab = 'storage')}
				>
					스토리지 현황
				</button>
				<button
					type="button"
					class="px-3 py-2 text-sm rounded-md transition {activeTab === 'cleanup'
						? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
						: 'text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200'}"
					on:click={() => (activeTab = 'cleanup')}
				>
					데이터 삭제
				</button>
			</div>

			<!-- 사용자 통계 탭 -->
			{#if activeTab === 'usage'}
				<div class="space-y-3">
					<div class="text-sm font-medium">사용자 통계</div>

				<!-- 날짜/시간 선택 -->
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="block text-xs font-medium mb-1">시작일</label>
					<input
						type="date"
						bind:value={startDate}
						class="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md"
					/>
				</div>
				<div>
					<label class="block text-xs font-medium mb-1">종료일</label>
					<input
						type="date"
						bind:value={endDate}
						class="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md"
					/>
				</div>
				<div>
					<label class="block text-xs font-medium mb-1">시작시간</label>
					<input
						type="time"
						step="60"
						bind:value={startTime}
						class="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md"
					/>
				</div>
				<div>
					<label class="block text-xs font-medium mb-1">종료시간</label>
					<input
						type="time"
						step="60"
						bind:value={endTime}
						class="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md"
					/>
				</div>
			</div>

			<!-- 필터: 소속 / 본부 / 부문 -->
			<div class="grid grid-cols-3 gap-3">
				<div>
					<label class="block text-xs font-medium mb-1">소속</label>
					<input
						type="text"
						placeholder="전체"
						bind:value={filterTeam}
						class="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md"
					/>
				</div>
				<div>
					<label class="block text-xs font-medium mb-1">본부</label>
					<input
						type="text"
						placeholder="전체"
						bind:value={filterHQ}
						class="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md"
					/>
				</div>
				<div>
					<label class="block text-xs font-medium mb-1">부문</label>
					<input
						type="text"
						placeholder="전체"
						bind:value={filterDivision}
						class="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md"
					/>
				</div>
			</div>

				<!-- 통계 조회/익스포트 버튼 -->
				<div class="flex gap-2">
					<button
						type="button"
						class="flex-1 py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md transition"
						on:click={fetchUsageStats}
						disabled={loading}
					>
						{loading ? '조회중...' : '통계 조회'}
					</button>
					<button
						type="button"
						class="py-2 px-3 bg-green-600 hover:bg-green-700 text-white text-sm rounded-md transition"
						on:click={exportStats}
					>
						Excel 다운로드
					</button>
				</div>

				<!-- 통계 결과 테이블 -->
				{#if statsData}
					<div class="mt-4 space-y-3">
						<div class="text-sm text-gray-600 dark:text-gray-400">
							총 {statsData.total}명 (페이지 {statsData.page} / {Math.ceil(statsData.total / pageSize)})
						</div>
						
						<div class="overflow-x-auto">
							<table class="w-full text-sm border border-gray-200 dark:border-gray-700 rounded-md">
								<thead class="bg-gray-50 dark:bg-gray-900">
									<tr>
										<th class="px-3 py-2 text-left font-medium">이름</th>
										<th class="px-3 py-2 text-left font-medium">이메일</th>
										<th class="px-3 py-2 text-left font-medium">소속</th>
										<th class="px-3 py-2 text-left font-medium">본부</th>
										<th class="px-3 py-2 text-left font-medium">부문</th>
										<th class="px-3 py-2 text-left font-medium">직급</th>
										<th class="px-3 py-2 text-right font-medium">메시지 수</th>
										<th class="px-3 py-2 text-right font-medium">파일 업로드</th>
									</tr>
								</thead>
								<tbody>
									{#each statsData.users as user, i}
										<tr class="border-t border-gray-200 dark:border-gray-700 {i % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-gray-50 dark:bg-gray-900'}">
											<td class="px-3 py-2">{user.name}</td>
											<td class="px-3 py-2">{user.email}</td>
											<td class="px-3 py-2">{user.team || ''}</td>
											<td class="px-3 py-2">{user.headquarters || ''}</td>
											<td class="px-3 py-2">{user.division || ''}</td>
											<td class="px-3 py-2">{user.position || ''}</td>
											<td class="px-3 py-2 text-right">{user.message_count}</td>
											<td class="px-3 py-2 text-right">{user.file_upload_count}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>

						<!-- 페이지네이션 -->
						{#if Math.ceil(statsData.total / pageSize) > 1}
							<div class="flex justify-center space-x-2 mt-3">
								<button
									type="button"
									class="px-3 py-1 text-sm border rounded {currentPage === 1 ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}"
									on:click={() => changePage(currentPage - 1)}
									disabled={currentPage === 1}
								>
									이전
								</button>
								
								{#each Array(Math.ceil(statsData.total / pageSize)).fill(0) as _, i}
									<button
										type="button"
										class="px-3 py-1 text-sm border rounded {currentPage === i + 1 ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}"
										on:click={() => changePage(i + 1)}
									>
										{i + 1}
									</button>
								{/each}
								
								<button
									type="button"
									class="px-3 py-1 text-sm border rounded {currentPage === Math.ceil(statsData.total / pageSize) ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}"
									on:click={() => changePage(currentPage + 1)}
									disabled={currentPage === Math.ceil(statsData.total / pageSize)}
								>
									다음
								</button>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/if}

		<!-- 파일 스토리지 분석 탭 -->
		{#if activeTab === 'storage'}
			<div class="space-y-3">
				<div class="text-sm font-medium">파일 스토리지 현황</div>

				<!-- 조회 버튼 -->
				<button
					type="button"
					class="w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md transition"
					on:click={fetchFileStorageStats}
					disabled={storageLoading}
				>
					{storageLoading ? '조회중...' : '스토리지 현황 조회'}
				</button>

				<!-- 스토리지 통계 결과 -->
				{#if storageStats}
					<div class="mt-4 space-y-4">
						<div class="text-sm text-gray-600 dark:text-gray-400">
							현재 스토리지 현황
						</div>

						<!-- 업로드 파일 정보 -->
						<div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
							<h4 class="font-medium text-blue-800 dark:text-blue-200 mb-3">📁 업로드 파일</h4>
							<div class="grid grid-cols-2 gap-4 text-sm">
								<div>
									<div class="text-gray-600 dark:text-gray-400">파일 개수</div>
									<div class="font-semibold text-blue-700 dark:text-blue-300">
										{storageStats.uploads.total_count}개
									</div>
								</div>
								<div>
									<div class="text-gray-600 dark:text-gray-400">총 용량</div>
									<div class="font-semibold text-blue-700 dark:text-blue-300">
										{storageStats.uploads.total_size_formatted}
									</div>
								</div>
							</div>

							<!-- 용량 상위 5개 파일 -->
							{#if storageStats.uploads.top_files && storageStats.uploads.top_files.length > 0}
								<div class="mt-4 pt-3 border-t border-blue-200 dark:border-blue-700">
									<div class="text-sm font-medium text-blue-800 dark:text-blue-200 mb-2">
										용량 상위 파일
									</div>
									<div class="space-y-1 max-h-32 overflow-y-auto">
										{#each storageStats.uploads.top_files as file}
											<div class="flex justify-between items-center text-xs bg-blue-100 dark:bg-blue-800/30 rounded p-2">
												<div class="flex-1 truncate pr-2" title={file.path}>
													<span class="font-medium">{file.name}</span>
													<div class="text-gray-500 dark:text-gray-400 text-xs truncate">
														{file.path}
													</div>
												</div>
												<div class="font-semibold text-blue-700 dark:text-blue-300">
													{file.size_formatted}
												</div>
											</div>
										{/each}
									</div>
								</div>
							{/if}

							<div class="text-xs text-gray-500 dark:text-gray-400 mt-3">
								경로: {storageStats.uploads.directory_path}
							</div>
						</div>

						<!-- 벡터 데이터베이스 정보 -->
						<div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
							<h4 class="font-medium text-green-800 dark:text-green-200 mb-3">🗂️ 벡터 데이터베이스</h4>
							<div class="grid grid-cols-2 gap-4 text-sm">
								<div>
									<div class="text-gray-600 dark:text-gray-400">컬렉션 수</div>
									<div class="font-semibold text-green-700 dark:text-green-300">
										{storageStats.vector_db.collection_count}개
									</div>
								</div>
								<div>
									<div class="text-gray-600 dark:text-gray-400">전체 크기</div>
									<div class="font-semibold text-green-700 dark:text-green-300">
										{storageStats.vector_db.total_size_formatted}
									</div>
								</div>
							</div>
						</div>

						<!-- 데이터베이스 파일 정보 -->
						<div class="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg p-4">
							<h4 class="font-medium text-purple-800 dark:text-purple-200 mb-3">🗄️ 데이터베이스</h4>
							<div class="text-sm">
								<div class="text-gray-600 dark:text-gray-400">webui.db 용량</div>
								<div class="font-semibold text-purple-700 dark:text-purple-300">
									{storageStats.database.webui_db.size_formatted}
								</div>
								{#if !storageStats.database.webui_db.exists}
									<div class="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
										⚠️ 데이터베이스 파일을 찾을 수 없습니다
									</div>
								{:else}
									<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
										경로: {storageStats.database.webui_db.path}
									</div>
								{/if}
							</div>
						</div>
					</div>
				{/if}
			</div>
		{/if}

		<!-- 데이터 삭제 탭 -->
		{#if activeTab === 'cleanup'}
			<div class="space-y-4">
				<div class="text-sm font-medium text-red-600 dark:text-red-400">⚠️ 데이터 삭제</div>
				<div class="text-xs text-gray-600 dark:text-gray-400">
					지정된 날짜/시간 이전의 파일과 벡터 데이터를 영구적으로 삭제합니다.
					<strong>삭제된 데이터는 복구할 수 없습니다.</strong>
				</div>

				<!-- 삭제 기준 설정 -->
				<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
					<h4 class="font-medium text-red-800 dark:text-red-200 mb-3">삭제 기준 설정</h4>

					<div class="grid grid-cols-2 gap-3 mb-3">
						<div>
							<label class="block text-xs font-medium mb-1">기준 날짜</label>
							<input
								type="date"
								bind:value={cleanupCutoffDate}
								class="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md"
							/>
						</div>
						<div>
							<label class="block text-xs font-medium mb-1">기준 시간</label>
							<input
								type="time"
								step="1"
								bind:value={cleanupCutoffTime}
								class="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md"
							/>
						</div>
					</div>

					<!-- 삭제 옵션 -->
					<div class="space-y-2 mb-3">
						<label class="flex items-center text-sm">
							<input type="checkbox" bind:checked={deleteFiles} class="mr-2" />
							업로드된 파일 삭제
						</label>
						<label class="flex items-center text-sm">
							<input type="checkbox" bind:checked={deleteVectors} class="mr-2" />
							벡터 데이터 삭제
						</label>
						<label class="flex items-center text-sm">
							<input type="checkbox" bind:checked={deleteDbRecords} class="mr-2" />
							데이터베이스 레코드 삭제
						</label>
					</div>


					<!-- 미리보기 버튼 -->
					<button
						type="button"
						class="w-full py-2 px-3 bg-orange-600 hover:bg-orange-700 text-white text-sm rounded-md transition"
						on:click={fetchCleanupPreview}
						disabled={cleanupLoading}
					>
						{cleanupLoading ? '조회중...' : '삭제 대상 미리보기'}
					</button>
				</div>

				<!-- 미리보기 결과 -->
				{#if cleanupPreview}
					<div class="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg p-4">
						<h4 class="font-medium text-orange-800 dark:text-orange-200 mb-3">삭제 대상 미리보기</h4>

						<div class="text-sm mb-3">
							<strong>기준 시점:</strong> {cleanupPreview.cutoff_datetime}
						</div>

						{#if cleanupPreview.files}
							<div class="mb-3">
								<div class="text-sm font-medium text-orange-700 dark:text-orange-300">📁 업로드 파일</div>
								<div class="text-xs text-gray-600 dark:text-gray-400">
									{cleanupPreview.files.count}개 파일, {cleanupPreview.files.total_size_formatted}
								</div>
								{#if cleanupPreview.files.files && cleanupPreview.files.files.length > 0}
									<div class="mt-2 max-h-32 overflow-y-auto">
										{#each cleanupPreview.files.files as file}
											<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
												{file.filename} ({file.size_formatted || 'unknown size'})
											</div>
										{/each}
										{#if cleanupPreview.files.count > 10}
											<div class="text-xs text-gray-400 italic">
												... 외 {cleanupPreview.files.count - 10}개 파일
											</div>
										{/if}
									</div>
								{/if}
							</div>
						{/if}

						{#if cleanupPreview.vector_collections}
							<div class="mb-3">
								<div class="text-sm font-medium text-orange-700 dark:text-orange-300">🗂️ 벡터 컬렉션</div>
								<div class="text-xs text-gray-600 dark:text-gray-400">
									{cleanupPreview.vector_collections.count}개 컬렉션, {cleanupPreview.vector_collections.total_size_formatted}
								</div>
								{#if cleanupPreview.vector_collections.collections && cleanupPreview.vector_collections.collections.length > 0}
									<div class="mt-2 max-h-32 overflow-y-auto">
										{#each cleanupPreview.vector_collections.collections as collection}
											<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
												{collection.name} ({collection.size_formatted || 'unknown size'})
											</div>
										{/each}
									</div>
								{/if}
							</div>
						{/if}


						{#if cleanupPreview.chat_mapping}
							<div class="mb-3">
								<div class="text-sm font-medium text-orange-700 dark:text-orange-300">🔗 채팅 매핑 파일</div>
								{#if cleanupPreview.chat_mapping.error}
									<div class="text-xs text-red-600 dark:text-red-400">
										❌ {cleanupPreview.chat_mapping.error}
									</div>
								{:else if cleanupPreview.chat_mapping.status === 'not_found'}
									<div class="text-xs text-yellow-600 dark:text-yellow-400">
										⚠️ 매핑 파일을 찾을 수 없음: {cleanupPreview.chat_mapping.path}
									</div>
								{:else}
									<div class="text-xs text-gray-600 dark:text-gray-400">
										📁 {cleanupPreview.chat_mapping.path}<br>
										전체: {cleanupPreview.chat_mapping.total}개, 삭제 예정: {cleanupPreview.chat_mapping.to_remove}개
									</div>
								{/if}
							</div>
						{/if}

						<!-- 삭제 실행 버튼 -->
						<div class="flex gap-2 mt-4">
							<button
								type="button"
								class="flex-1 py-2 px-3 bg-red-600 hover:bg-red-700 text-white text-sm rounded-md transition"
								on:click={() => (showCleanupConfirm = true)}
								disabled={cleanupLoading}
							>
								삭제 실행
							</button>
							<button
								type="button"
								class="py-2 px-3 bg-gray-500 hover:bg-gray-600 text-white text-sm rounded-md transition"
								on:click={() => executeCleanup(true)}
								disabled={cleanupLoading}
							>
								테스트 실행
							</button>
						</div>
					</div>
				{/if}

				<!-- 삭제 결과 -->
				{#if cleanupResult}
					<div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
						<h4 class="font-medium text-green-800 dark:text-green-200 mb-3">삭제 완료</h4>

						<div class="text-sm mb-2">
							<strong>실행 시간:</strong> {cleanupResult.started_at} ~ {cleanupResult.completed_at}
						</div>

						{#if cleanupResult.files}
							<div class="text-sm">
								<strong>파일:</strong> {cleanupResult.files.total_files_deleted}개 삭제
								({cleanupResult.files.total_size_deleted_formatted})
								{#if cleanupResult.files.failed_files && cleanupResult.files.failed_files.length > 0}
									<span class="text-red-600">({cleanupResult.files.failed_files.length}개 실패)</span>
								{/if}
							</div>
						{/if}

						{#if cleanupResult.vector_collections}
							<div class="text-sm">
								<strong>벡터 컬렉션:</strong> {cleanupResult.vector_collections.total_collections_deleted}개 삭제
								({cleanupResult.vector_collections.total_size_deleted_formatted})
								{#if cleanupResult.vector_collections.failed_collections && cleanupResult.vector_collections.failed_collections.length > 0}
									<span class="text-red-600">({cleanupResult.vector_collections.failed_collections.length}개 실패)</span>
								{/if}
							</div>
						{/if}


					</div>
				{/if}

				<!-- 확인 모달 -->
				{#if showCleanupConfirm}
					<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
						<div class="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
							<h3 class="text-lg font-semibold text-red-600 dark:text-red-400 mb-4">⚠️ 데이터 삭제 확인</h3>
							<p class="text-sm text-gray-700 dark:text-gray-300 mb-4">
								정말로 선택한 데이터를 삭제하시겠습니까?
								<strong>이 작업은 되돌릴 수 없습니다.</strong>
							</p>
							<!-- 최종 확인용 비밀번호 입력 필드 (모달 내부) -->
							<div class="mb-4">
								<label class="block text-xs font-medium mb-1">현재 비밀번호</label>
								<input
									type="password"
									bind:value={confirmPassword}
									placeholder="삭제를 진행하려면 비밀번호를 입력하세요"
									class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md text-sm bg-white dark:bg-gray-800"
								/>
								<p class="text-[11px] text-gray-500 mt-1">관리자 계정의 현재 비밀번호를 입력해야 삭제가 진행됩니다.</p>
							</div>
							<div class="flex gap-2">
								<button
									type="button"
									class="flex-1 py-2 px-3 bg-red-600 hover:bg-red-700 text-white text-sm rounded-md transition"
									on:click={() => executeCleanup(false)}
									disabled={cleanupLoading}
								>
									삭제 실행
								</button>
								<button
									type="button"
									class="py-2 px-3 bg-gray-500 hover:bg-gray-600 text-white text-sm rounded-md transition"
									on:click={() => (showCleanupConfirm = false)}
								>
									취소
								</button>
							</div>
						</div>
					</div>
				{/if}
			</div>

				<button
					class=" flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					on:click={() => {
						exportUsers();
					}}
				>
					<div class=" self-center mr-3">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
							<path
								fill-rule="evenodd"
								d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
					<div class=" self-center text-sm font-medium">
						{$i18n.t('Export Users')}
					</div>
				</button>
		{/if}
		</div>
	</div>
</form>
