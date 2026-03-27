<section class="py-20 md:py-28 px-4">
	<div class="max-w-5xl mx-auto">
		<div class="scroll-reveal text-center mb-14">
			<h2 class="text-2xl md:text-4xl font-bold mb-3">Sound familiar?</h2>
			<p class="text-white/40">Every unanswered review is a customer choosing your competitor.</p>
		</div>

		<div class="grid md:grid-cols-3 gap-5">
			{#each [
				{ icon: '2', color: 'from-rose-500/20 to-rose-500/5', border: 'border-rose-500/10', title: 'Bad review sitting there', desc: 'Got a 2-star review last week. Still haven\'t replied. Don\'t know what to say without making it worse.' },
				{ icon: '0', color: 'from-amber-500/20 to-amber-500/5', border: 'border-amber-500/10', title: 'No time to reply', desc: 'You\'re running a business. Writing thoughtful, unique replies to every review takes hours you don\'t have.' },
				{ icon: '#', color: 'from-blue-500/20 to-blue-500/5', border: 'border-blue-500/10', title: 'Competitors rank higher', desc: 'Google promotes businesses that respond to reviews. Your silence is literally pushing customers away.' }
			] as card, i}
				<div class="scroll-reveal scroll-reveal-delay-{i + 1} group bg-gradient-to-br {card.color} rounded-2xl p-7 border {card.border} hover:scale-[1.02] transition-all duration-300">
					<div class="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center text-lg font-bold text-white/40 mb-4 group-hover:text-white/60 transition">{card.icon}</div>
					<h3 class="font-bold text-lg mb-2">{card.title}</h3>
					<p class="text-sm text-white/40 leading-relaxed">{card.desc}</p>
				</div>
			{/each}
		</div>
	</div>
</section>
