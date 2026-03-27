<section class="py-20 px-4">
	<div class="max-w-5xl mx-auto">
		<div class="scroll-reveal text-center mb-4">
			<h2 class="text-2xl md:text-4xl font-bold mb-3">The data is clear</h2>
			<p class="text-white/40">Replying to reviews isn't optional anymore.</p>
		</div>

		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-12">
			{#each [
				{ value: '+45%', label: 'more likely to visit', sub: 'when you reply to reviews', gradient: 'from-blue-400 to-cyan-400' },
				{ value: '89%', label: 'of consumers read', sub: 'business responses first', gradient: 'from-violet-400 to-pink-400' },
				{ value: '#1', label: 'Google ranking factor', sub: 'review activity & replies', gradient: 'from-emerald-400 to-cyan-400' },
				{ value: '4.8', label: 'avg rating after 6mo', sub: 'of responding to all reviews', gradient: 'from-amber-400 to-orange-400' }
			] as stat, i}
				<div class="scroll-reveal scroll-reveal-delay-{i + 1} bg-white/[0.03] border border-white/5 rounded-2xl p-6 text-center hover:bg-white/[0.05] hover:border-white/10 transition-all duration-300 group">
					<div class="text-3xl md:text-4xl font-black bg-gradient-to-r {stat.gradient} bg-clip-text text-transparent mb-2 group-hover:scale-110 transition-transform">{stat.value}</div>
					<div class="text-sm font-medium text-white/60 mb-1">{stat.label}</div>
					<div class="text-xs text-white/25">{stat.sub}</div>
				</div>
			{/each}
		</div>
	</div>
</section>
