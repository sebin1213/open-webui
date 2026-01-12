<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import Checkbox from '$lib/components/common/Checkbox.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import Search from '$lib/components/icons/Search.svelte';

	export let users = [];
	export let userIds = [];

	let filteredUsers = [];

	$: filteredUsers = users
		.filter((user) => {
			if (query === '') {
				return true;
			}

			return (
				user.name.toLowerCase().includes(query.toLowerCase()) ||
				user.email.toLowerCase().includes(query.toLowerCase()) ||
				user.info?.team?.toLowerCase().includes(query.toLowerCase()) ||
				user.info?.headquarters?.toLowerCase().includes(query.toLowerCase()) ||
				user.info?.division?.toLowerCase().includes(query.toLowerCase()) ||
				user.info?.position?.toLowerCase().includes(query.toLowerCase())
			);
		})
		.sort((a, b) => {
			const aUserIndex = userIds.indexOf(a.id);
			const bUserIndex = userIds.indexOf(b.id);

			// Compare based on userIds or fall back to alphabetical order
			if (aUserIndex !== -1 && bUserIndex === -1) return -1; // 'a' has valid userId -> prioritize
			if (bUserIndex !== -1 && aUserIndex === -1) return 1; // 'b' has valid userId -> prioritize

			// Both a and b are either in the userIds array or not, so we'll sort them by their indices
			if (aUserIndex !== -1 && bUserIndex !== -1) return aUserIndex - bUserIndex;

			// If both are not in the userIds, fallback to alphabetical sorting by name
			return a.name.localeCompare(b.name);
		});

	let query = '';
</script>

<div>
	<div class="flex w-full">
		<div class="flex flex-1">
			<div class=" self-center mr-3">
				<Search />
			</div>
			<input
				class=" w-full text-sm pr-4 rounded-r-xl outline-hidden bg-transparent"
				bind:value={query}
				placeholder={$i18n.t('Search')}
			/>
		</div>
	</div>

	<div class="mt-3 scrollbar-hidden">
		<div class="flex flex-col gap-2.5">
			{#if filteredUsers.length > 0}
				{#each filteredUsers as user, userIdx (user.id)}
					<div class="flex flex-row items-start gap-3 w-full text-sm py-2 px-1 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
						<div class="flex items-center mt-1">
							<Checkbox
								state={userIds.includes(user.id) ? 'checked' : 'unchecked'}
								on:change={(e) => {
									if (e.detail === 'checked') {
										userIds = [...userIds, user.id];
									} else {
										userIds = userIds.filter((id) => id !== user.id);
									}
								}}
							/>
						</div>

						<div class="flex flex-col flex-1 min-w-0">
							<div class="flex items-center justify-between">
								<div class="font-medium text-gray-900 dark:text-gray-100 truncate">
									{user.name}
								</div>
								{#if userIds.includes(user.id)}
									<Badge type="success" content="member" />
								{/if}
							</div>
							
							<div class="text-xs text-gray-600 dark:text-gray-400 mt-1 truncate">
								{user.email}
							</div>
							
							{#if user.info?.team || user.info?.headquarters || user.info?.division || user.info?.position}
								<div class="flex flex-wrap gap-1 mt-1">
									{#if user.info?.team}
										<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
											{user.info.team}
										</span>
									{/if}
									{#if user.info?.headquarters}
										<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">
											{user.info.headquarters}
										</span>
									{/if}
									{#if user.info?.division}
										<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
											{user.info.division}
										</span>
									{/if}
									{#if user.info?.position}
										<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
											{user.info.position}
										</span>
									{/if}
								</div>
							{/if}
						</div>
					</div>
				{/each}
			{:else}
				<div class="text-gray-500 text-xs text-center py-2 px-10">
					{$i18n.t('No users were found.')}
				</div>
			{/if}
		</div>
	</div>
</div>
