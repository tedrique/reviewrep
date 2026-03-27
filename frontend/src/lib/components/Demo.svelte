<script lang="ts">
	import { onMount } from 'svelte';

	let typing = $state(false);
	let responseText = $state('');
	let showResponse = $state(false);
	let showButtons = $state(false);

	const fullResponse = `Hi Sarah, thank you for letting us know. We're genuinely sorry about the long wait and the food not being up to standard — that's not the experience we want for our guests. We've raised this directly with our kitchen team. We'd love the chance to make it right — please don't hesitate to reach out to us directly.`;

	function typeResponse() {
		typing = true;
		showResponse = true;
		let i = 0;
		const interval = setInterval(() => {
			responseText = fullResponse.slice(0, i);
			i += 2;
			if (i > fullResponse.length) {
				responseText = fullResponse;
				clearInterval(interval);
				typing = false;
				setTimeout(() => showButtons = true, 300);
			}
		}, 15);
	}
</script>

<section id="demo" class="py-20 md:py-32 px-4">
	<div class="max-w-4xl mx-auto">
		<div class="scroll-reveal text-center mb-12">
			<h2 class="text-2xl md:text-4xl font-bold mb-3">See it in action</h2>
			<p class="text-white/40">Real review. Real AI response. Real time.</p>
		</div>

		<div class="scroll-reveal scroll-reveal-delay-1">
			<!-- Browser window -->
			<div class="rounded-2xl border border-white/10 bg-white/[0.02] backdrop-blur-sm overflow-hidden shadow-2xl shadow-blue-500/5">
				<!-- Browser bar -->
				<div class="flex items-center gap-2 px-4 py-3 border-b border-white/5 bg-white/[0.02]">
					<div class="flex gap-1.5">
						<div class="w-3 h-3 rounded-full bg-white/10"></div>
						<div class="w-3 h-3 rounded-full bg-white/10"></div>
						<div class="w-3 h-3 rounded-full bg-white/10"></div>
					</div>
					<div class="flex-1 mx-4">
						<div class="bg-white/5 rounded-lg px-3 py-1 text-xs text-white/30 text-center">reviewrep.me/dashboard</div>
					</div>
				</div>

				<div class="p-6 md:p-8 space-y-5">
					<!-- Review card -->
					<div class="bg-gradient-to-br from-amber-500/10 to-orange-500/5 rounded-xl p-5 border border-amber-500/10">
						<div class="flex items-center justify-between mb-3">
							<div class="flex items-center gap-2">
								<div class="w-8 h-8 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-xs font-bold text-black">S</div>
								<span class="font-semibold text-sm">Sarah M.</span>
							</div>
							<div class="flex gap-0.5">
								<span class="text-amber-400">&#9733;&#9733;</span><span class="text-white/20">&#9733;&#9733;&#9733;</span>
							</div>
						</div>
						<p class="text-sm text-white/70 leading-relaxed">"Waited 40 minutes for our food and when it arrived it was cold. Really disappointing as we'd heard good things."</p>
					</div>

					<!-- AI Response -->
					{#if !showResponse}
						<button onclick={typeResponse} class="w-full py-4 rounded-xl bg-gradient-to-r from-blue-500/20 to-violet-500/20 border border-blue-500/20 text-blue-400 font-medium hover:from-blue-500/30 hover:to-violet-500/30 transition-all cursor-pointer hover:scale-[1.01]">
							Generate AI Response
						</button>
					{:else}
						<div class="bg-gradient-to-br from-blue-500/10 to-violet-500/5 rounded-xl p-5 border border-blue-500/10 transition-all duration-500">
							<div class="flex items-center gap-2 mb-3">
								<div class="w-2 h-2 rounded-full {typing ? 'bg-blue-400 animate-pulse' : 'bg-emerald-400'}"></div>
								<span class="text-xs font-medium {typing ? 'text-blue-400' : 'text-emerald-400'}">{typing ? 'AI writing...' : 'Response ready'}</span>
							</div>
							<p class="text-sm text-white/70 leading-relaxed italic">{responseText}{#if typing}<span class="animate-pulse">|</span>{/if}</p>

							{#if showButtons}
								<div class="flex gap-2 mt-4 animate-fade-up">
									<button class="px-4 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/20 text-emerald-400 text-xs font-medium hover:bg-emerald-500/30 transition">Approve</button>
									<button class="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white/40 text-xs font-medium hover:bg-white/10 transition">Edit</button>
									<button class="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white/40 text-xs font-medium hover:bg-white/10 transition">Regenerate</button>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			</div>
		</div>
	</div>
</section>
